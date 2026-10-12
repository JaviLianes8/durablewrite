# durablewrite guide

This guide explains what `durablewrite` does on every write, what it guarantees
on each platform, and where those guarantees stop. Each claim cites its source
or the test in this repository that exercises it.

## The write protocol

For `atomic_write(path)` and every helper built on it:

1. **Resolve the target.** If `path` is a symlink and `follow_symlinks=True`
   (the default), the file it points to becomes the target, so the link keeps
   working. With `follow_symlinks=False` the link itself is replaced by a
   regular file. An existing directory is rejected with `IsADirectoryError`.
2. **Create a temp file in the target's own directory**, named
   `.<name>.<8 hex digits>.dwtmp`, with `O_CREAT | O_EXCL` and mode `0o666`, so
   the process umask applies exactly as it does for `open()`. Same directory
   means same filesystem, which `rename` needs to be atomic: Python documents
   that `os.replace` "may fail if src and dst are on different filesystems" [1].
3. **Write** your data into it.
4. **Set metadata.** With `preserve_owner=True` (POSIX) the uid and gid of the
   old file are copied first, then the permission bits: either `permissions`
   or, with `preserve_mode=True` (the default), the bits of the old file.
5. **Flush and fsync the temp file** (`fsync="file"` or `"full"`). This must
   happen before the rename: otherwise the new name can reach disk before the
   data it points to, which is how ext4 and XFS produced empty or zero-filled
   files after a crash [3][4][5].
6. **Rename** the temp file onto the target with `os.replace`. With
   `overwrite=False`, a create-only rename is used instead (see below).
7. **Fsync the parent directory** (`fsync="full"`, POSIX only) so the rename
   itself is on disk. Linux `fsync(2)`: "Calling fsync() does not necessarily
   ensure that the entry in the directory containing the file has also reached
   disk. For that an explicit fsync() on a file descriptor for the directory is
   also needed." [2][3]

If anything raises before step 6 completes, the temp file is removed and the
target is untouched. That includes exceptions inside your `with` block and
`KeyboardInterrupt`.

## What is guaranteed, per platform

| Promise | Linux / macOS (local fs) | Windows (local NTFS) |
| --- | --- | --- |
| Readers see the old or the complete new file, never a mix | Yes, `rename(2)` is atomic by POSIX [6] | Yes on NTFS in our tests; not documented as atomic by Microsoft [7] |
| A killed writer leaves the old or the new file, never a partial one | Yes (tested) | Yes (tested) |
| New content survives power loss once the call returns (`"full"`) | Linux: yes, file and directory are fsynced. macOS: see below | File data is flushed with `FlushFileBuffers` [8]; the rename is not explicitly flushed |
| Permission bits kept on replace | Yes (`preserve_mode`) | Not applicable; see below |
| Owner kept on replace | Opt-in (`preserve_owner`), needs privilege to change uid | No |
| Replace while another process has the target open | Yes; the reader keeps the old inode | Retried, then `SharingViolationError` |

The crash and concurrency rows are exercised by `tests/test_crash.py` and
`tests/test_concurrency.py`, which run on both Windows (NTFS) and Linux (ext4)
in this project's local gate.

### Process crash versus power loss

The kill-mid-write test terminates a writer process at random moments (seeded,
`DURABLEWRITE_CRASH_SEED`) and checks that the target is always a complete,
checksummed payload. That proves atomicity against a process crash. No portable
test can cut the power, so durability against power loss rests on the fsync
calls above and on the filesystem honouring them [3].

### Linux

`fsync="full"` follows the sequence recommended in "Ensuring data reaches disk"
[3]: fsync the file, rename, fsync the directory. Do not rely on ext4's
`auto_da_alloc` heuristic for "replace via rename" [4]; it is a mount option and
other filesystems such as XFS have no equivalent [5]. If the directory fsync
raises (some network and FUSE filesystems refuse it), the new content is
already in place and the error is reported to you.

### macOS

On macOS `fsync` hands the data to the drive but does not ask the drive to
flush its own write cache; Apple documents `F_FULLFSYNC` for that [9].
`durablewrite` calls `os.fsync` and does not issue `F_FULLFSYNC`, so on macOS
`"full"` protects against an OS crash but not necessarily against a power loss
with an unflushed drive cache.

### Windows

- `os.replace` is `MoveFileExW(src, dst, MOVEFILE_REPLACE_EXISTING)` [1][7].
  Microsoft does not document it as atomic. On a local NTFS volume the rename is
  a single metadata operation and our tests never observed a torn or missing
  target. On FAT volumes and SMB shares the behaviour depends on the
  filesystem or server and is not guaranteed.
- `os.fsync` calls the CRT `_commit`, which calls `FlushFileBuffers` [8][10].
- There is no directory fsync on Windows through the APIs Python exposes, so
  `"full"` behaves like `"file"`. The data of the new file is flushed before
  the rename; the rename itself becomes durable when NTFS commits its journal.
- `MoveFileExW` fails with `ERROR_ACCESS_DENIED`, `ERROR_SHARING_VIOLATION` or
  `ERROR_LOCK_VIOLATION` while any process holds the target open without
  `FILE_SHARE_DELETE` [11]. Python's `open()` does not pass that flag, and
  antivirus scanners and the search indexer briefly open new files. These
  errors are retried with bounded backoff (`RetryPolicy`, about 1.1 seconds by
  default). A read-only target is never retried. When the budget runs out,
  `SharingViolationError` is raised, the target is untouched and the temp file
  is removed (`tests/test_sharing.py`).
- Permission bits do not exist on Windows. `permissions` only toggles the
  read-only attribute and `preserve_mode` does nothing. The new file inherits
  the ACL of its directory; an explicit ACL on the old file is not copied.

### Why not `ReplaceFileW`

`ReplaceFileW` [12] keeps the replaced file's ACL, attributes and creation
time, but it requires the target to exist and it can fail half way: its
documented `ERROR_UNABLE_TO_MOVE_REPLACEMENT_2` result leaves the target under
the backup name. A primitive whose failure mode removes the target conflicts
with the core promise, so `durablewrite` uses `MoveFileExW`.

## Create only if absent

`overwrite=False` publishes the complete file only if nothing exists at the
target, and raises `FileExistsError` otherwise, without a check-then-act race:

- POSIX: `link(temp, target)` fails with `EEXIST` if the name is taken, then the
  temp name is unlinked. The filesystem must support hard links.
- Windows: `MoveFileExW` without `MOVEFILE_REPLACE_EXISTING` fails with
  `ERROR_ALREADY_EXISTS`.

`tests/test_overwrite.py` races six processes for one name and checks that
exactly one wins.

## Symlinks

The default (`follow_symlinks=True`) writes to the file the link points to and
creates the temp file beside that file, so the rename never crosses a
filesystem even when the link lives elsewhere. A dangling link creates its
target. `follow_symlinks=False` replaces the link with a regular file, which is
what plain `os.replace` does.

## Side effects of replacing a file

Replacing a file creates a new file, by design. As a consequence:

- Other hard links to the old file keep the old content.
- The inode (POSIX) or file ID (Windows) changes. Programs that follow a file
  by handle, such as `tail -f` without `-F`, keep reading the old file.
- Extended attributes, POSIX ACLs and Windows alternate data streams of the
  old file are not copied.

## Leftover temp files

A writer that is killed between creating its temp file and renaming it cannot
clean up. `cleanup_temp_files(directory, older_than=3600)` removes only regular
files matching `.<name>.<8 hex digits>.dwtmp` older than the given age, so live
writers are left alone. The crash test uses it to reclaim every temp file its
kills leave behind.

## Command line

`durablewrite TARGET` copies standard input into TARGET with the protocol
above, like `sponge` from moreutils. TARGET is replaced only after standard
input ends, so `sort f | durablewrite f` and `durablewrite --append f < f` are
safe. Run `durablewrite --help` for every option and examples. Every error,
including a usage error, exits with status 1 and leaves TARGET unchanged.

## Sources

1. Python documentation, `os.replace` and `os.fsync`:
   https://docs.python.org/3/library/os.html#os.replace
2. Linux `fsync(2)` manual page: https://man7.org/linux/man-pages/man2/fsync.2.html
3. Jeff Moyer, "Ensuring data reaches disk", LWN.net, 2011:
   https://lwn.net/Articles/457667/
4. Linux kernel documentation, ext4 mount options (`auto_da_alloc`):
   https://docs.kernel.org/admin-guide/ext4.html
5. XFS FAQ, "Why do I see binary NULLS in some files after recovery when I
   unplugged the power?": https://xfs.org/index.php/XFS_FAQ
6. POSIX.1-2024, `rename`:
   https://pubs.opengroup.org/onlinepubs/9799919799/functions/rename.html
7. Microsoft, `MoveFileExW`:
   https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw
8. Microsoft, `FlushFileBuffers`:
   https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers
9. Apple, `fsync(2)` manual page (`F_FULLFSYNC`):
   https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/fsync.2.html
10. Microsoft, `_commit`:
    https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/commit
11. Microsoft, `CreateFileW` (`FILE_SHARE_DELETE`):
    https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
12. Microsoft, `ReplaceFileW`:
    https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew
