# durablewrite guide

This guide explains what `durablewrite` does on every write, what it guarantees
on each platform, and where those guarantees stop. Each claim names its source
or the test in this repository that exercises it.

## The write protocol

For `atomic_write(path)` and every helper built on it:

1. **Check the arguments** when the writer is called, before any file is
   touched (see "Errors" below).
2. **Resolve the target.** If `path` is a symlink and `follow_symlinks=True`
   (the default), the file it points to becomes the target, so the link keeps
   working. With `follow_symlinks=False` the link itself is replaced by a
   regular file. An existing directory is rejected with `IsADirectoryError`, and
   with `overwrite=False` an existing name is rejected with `FileExistsError`,
   both before the block runs.
3. **Create a temp file in the target's own directory**, named
   `.<name>.<8 hex digits>.dwtmp`, with `O_CREAT | O_EXCL`. A new file is created
   with mode `0o666`, so the process umask applies exactly as it does for
   `open()`. When the final mode comes from `permissions` or from the replaced
   file, the temp file starts as `0o600` and is widened only after the data is
   written, so restricted content is never readable by others in between. Names
   longer than 48 characters keep a readable head plus a hash of the full name,
   so the temp name stays within the 255-byte limit. The same directory means
   the same filesystem, which the rename needs: Python documents that
   `os.replace` may fail across filesystems [1].
4. **Write** your data into it.
5. **Set metadata.** With `preserve_owner=True` (POSIX) the uid and gid of the
   old file are copied first, then the permission bits: either `permissions` or,
   with `preserve_mode=True` (the default), the bits of the old file.
6. **Flush the temp file to disk** (`fsync="file"` or `"full"`): `fsync` on
   Linux, `F_FULLFSYNC` on macOS, `FlushFileBuffers` on Windows. This must come
   before the rename, or the new name can reach the disk before the data it
   points to, which is how ext4 left zero-length files after a crash until it
   added a heuristic for that pattern [3][4].
7. **Rename** the temp file onto the target. With `overwrite=False` a
   create-only rename is used instead (see below).
8. **Make the rename durable** (`fsync="full"`). On POSIX the parent directory is
   fsynced: the Linux `fsync(2)` page says a file fsync does not by itself make
   the directory entry durable, and asks for an fsync of the directory [2][3].
   On Windows the rename of step 7 is made with `MOVEFILE_WRITE_THROUGH`, which
   Microsoft documents as not returning until the move is on the disk [6].

If anything raises before step 7 completes, the temp file is removed and the
target is untouched. That includes exceptions inside your `with` block and
`KeyboardInterrupt`.

## What is guaranteed, per platform

| Promise | Linux / macOS (local fs) | Windows (local NTFS) |
| --- | --- | --- |
| Readers see the old or the complete new file, never a mix | Yes, `rename(2)` replaces the name atomically [5][12] | Yes on NTFS in our tests; Microsoft does not call the rename atomic [6] |
| A killed writer leaves the old or the new file, never a partial one | Yes (tested at every call) | Yes (tested at every call) |
| New content survives power loss once the call returns (`"full"`) | Linux: data and directory fsynced. macOS: `F_FULLFSYNC` [8] | Data flushed [7]; rename written through [6] |
| Permission bits kept on replace | Yes (`preserve_mode`) | Not applicable; see below |
| Owner kept on replace | Opt-in (`preserve_owner`), needs privilege to change uid | No |
| Replace while another process has the target open | Yes; the reader keeps the old inode | Retried, then `SharingViolationError` |
| A reader can always open the target | Yes | No: an `open()` racing a rename can fail with `PermissionError` (never `FileNotFoundError`, never torn) |
| Replace a read-only target | Yes, if the directory is writable | No, `PermissionError` (not retried) |

### Process crash versus power loss

A process crash is tested directly. `tests/test_crash_points.py` runs a writer
that kills itself with no cleanup right before and right after each file system
call it makes, for every call, on Windows and POSIX. `tests/test_linux_trace.py`
does the same on Linux one level lower: an `LD_PRELOAD` library
(`tests/trace/dwtrace.c`) logs the real libc calls (`open`, `write`, `fsync`,
`rename`, `link`, `unlink`) and sends `SIGKILL` at each boundary. In every case
the target holds the old content until the rename has returned and the new
content from then on, and any leftover temp file is one that
`cleanup_temp_files` removes. `tests/test_crash.py` also kills writers at random
moments mid-write.

No portable test can cut the power, so durability against power loss rests on
the documented calls above and on the filesystem honouring them [3].

### Linux

`fsync="full"` follows the sequence recommended in "Ensuring data reaches disk"
[3]: fsync the file, rename, fsync the directory. The trace test records exactly
that order. Do not rely on ext4's `auto_da_alloc` heuristic for "replace via
rename" [4]; it is an ext4 mount option that can be turned off, not a promise of
the rename itself. If the directory fsync raises (some network and FUSE filesystems refuse it,
and it fails when the directory is writable but not readable), the new content is
already in place and `DirectorySyncError` is raised so you know the rename may
not be durable (`tests/test_hardening.py`).

### macOS

Apple documents that `fsync` hands the data to the drive without asking the
drive to empty its own write cache, and offers the `F_FULLFSYNC` fcntl for that
[8]. `durablewrite` issues `F_FULLFSYNC` for the file and for the directory, and
falls back to `fsync` on a filesystem that refuses it. This is the same choice
`atomicwrites` made. macOS was not part of this release's test runs; the code
path is pinned by `tests/test_contract_platform.py`.

### Windows

- `os.fsync` calls the C runtime's `_commit`, which flushes the file with
  `FlushFileBuffers` [1][7][9].
- With `fsync="full"`, the rename is `MoveFileExW` with
  `MOVEFILE_WRITE_THROUGH` (plus `MOVEFILE_REPLACE_EXISTING` unless
  `overwrite=False`) [6], as `atomicwrites` does. With `"file"` or `"none"` it is
  plain `os.replace`, which is `MoveFileExW` without write-through.
- There is no directory fsync through the APIs Python exposes; write-through
  takes its place.
- Microsoft does not document the rename as atomic. On a local NTFS volume it is
  a single metadata operation and our tests never observed a torn or missing
  target. On FAT volumes and SMB shares the behaviour depends on the filesystem
  or server and is not guaranteed.
- The rename fails with `ERROR_ACCESS_DENIED`, `ERROR_SHARING_VIOLATION` or
  `ERROR_LOCK_VIOLATION` while any process holds the target open without
  `FILE_SHARE_DELETE` [10]. Python's `open()` does not pass that flag, and
  antivirus scanners and the search indexer briefly open new files. These errors
  are retried with bounded backoff (`RetryPolicy`, about 1.1 seconds by default).
  A read-only target is never retried. Several processes replacing one file
  while others read it can keep it locked for longer than that on a slow or busy
  machine; give such writers a larger `RetryPolicy`. When the budget runs out,
  `SharingViolationError` is raised and the target is untouched
  (`tests/test_sharing.py`). A directory ACL that denies the rename produces the
  same error code and ends the same way.
- The temp file can itself be held open (an antivirus scan of the fresh file).
  On every error path its removal is retried under the same `RetryPolicy`; if it
  is still locked after that, it is left for `cleanup_temp_files`, which also
  clears a read-only attribute before removing.
- Permission bits do not exist on Windows. `permissions` only toggles the
  read-only attribute and `preserve_mode` does nothing. The new file inherits the
  ACL of its directory; an explicit ACL on the old file is not copied.

### Why not `ReplaceFileW`

`ReplaceFileW` [11] keeps the replaced file's ACL, attributes and creation time,
but it requires the target to exist and it can fail half way: Microsoft lists a
result, `ERROR_UNABLE_TO_MOVE_REPLACEMENT_2`, in which the replaced file is left
under another name. A primitive whose failure mode removes the target conflicts
with the core promise, so `durablewrite` uses `MoveFileExW`.

## Create only if absent

`overwrite=False` publishes the complete file only if nothing exists at the
target, and raises `FileExistsError` otherwise, without a check-then-act race:

- POSIX: `link(temp, target)` fails with `EEXIST` if the name is taken [13], then
  the temp name is unlinked. The filesystem must support hard links.
- Windows: `MoveFileExW` without `MOVEFILE_REPLACE_EXISTING` fails with error
  183 (`FileExistsError`), observed on NTFS (`tests/test_contract_platform.py`).

An existing name is refused before the block runs; a name that appears while
the block runs is refused by the rename. `tests/test_overwrite.py` races six
processes for one name and checks that exactly one wins.

## Symlinks

The default (`follow_symlinks=True`) writes to the file the link points to and
creates the temp file beside that file, so the rename never crosses a
filesystem even when the link lives elsewhere. A dangling link creates its
target. `follow_symlinks=False` replaces the link with a regular file, which is
what plain `os.replace` (and `atomicwrites`) does; on POSIX this also works when
the link points to a directory. The replaced link counts as a new file, so it
does not inherit the mode of whatever it pointed to.

## Side effects of replacing a file

Replacing a file creates a new file, by design. As a consequence:

- Other hard links to the old file keep the old content.
- The inode (POSIX) or file ID (Windows) changes. Programs that follow a file by
  handle, such as `tail -f` without `-F`, keep reading the old file.
- Extended attributes, POSIX ACLs and Windows alternate data streams of the old
  file are not copied.

## Leftover temp files

A writer that is killed between creating its temp file and renaming it cannot
clean up. `cleanup_temp_files(directory, older_than=3600)` removes only regular
files matching `.<name>.<8 hex digits>.dwtmp` older than the given age, by
modification time. A writer that keeps its temp file open for longer than that
age could lose it, so choose an age longer than your slowest write. With
`target=`, only temp files of that exact target name are considered. The age
must be a finite number of seconds, not negative: `NaN` once made every temp
file look stale, so it is refused.

## Errors

| Error | When |
| --- | --- |
| `TypeError` | a `bytes` path or another argument of the wrong type |
| `ValueError` | a bad `mode`, `fsync`, `newline`, `permissions`, retry setting or age; an empty path, a NUL in it, or one ending with a separator |
| `LookupError` | an unknown `encoding` |
| `IsADirectoryError` | the target is a directory |
| `FileExistsError` | `overwrite=False` and the name exists |
| `SharingViolationError` | Windows kept the rename blocked for the whole retry budget (a `PermissionError`) |
| `DirectorySyncError` | the file was replaced, but the directory fsync failed (POSIX, `"full"`) |
| other `OSError` | whatever the operating system reports: a missing directory, no space, no permission |

The first three are raised when the writer is called, before any file is
touched. Messages are short and never repeat the value they refuse.
`DurableWriteError` is the base of the two errors `durablewrite` raises itself
and is an `OSError`, so existing `except OSError` code keeps working.

## Command line

`durablewrite TARGET` copies standard input into TARGET with the protocol above,
like `sponge` from moreutils. TARGET is replaced only after standard input ends,
so `sort f | durablewrite f` is safe on every platform, and
`durablewrite --append f < f` works on POSIX. On Windows the shell (and the
console-script launcher) keep a redirected file open without
`FILE_SHARE_DELETE`, which blocks the rename, so the command detects that
standard input is TARGET and refuses at once; pipe the file instead.

Exit status: 0 on success; 1 on any error, including a usage error, with TARGET
left as it was; 3 when TARGET was replaced but its directory could not be
fsynced; 130 when interrupted. `--json` accepts only strict JSON (no `NaN` or
`Infinity`). Each `--append` run is atomic, but two concurrent runs on the same
file can lose one run's data, because each starts from the content it read.

## How this was checked

- **Documentation**: `tests/oracle/MANIFEST.json` lists every page cited below
  with its URL, fetch date, size and hash; `scripts/fetch_oracles.py` downloads
  them into a local folder that is never committed, and `tests/test_sources.py`
  checks that each still names the calls and flags this guide relies on.
- **System calls**: `tests/test_linux_trace.py` (Linux, needs gcc) records the
  real call order for each fsync level and kills the writer at every call.
- **Reference library**: `atomicwrites` 1.4.1 ran 120 scenarios (new file,
  replace, create-only, directory, symlink, dangling link, failing block, text and
  binary) on Windows and Linux; `tests/fixtures/atomicwrites-*.json` is its
  recorded output, and `tests/test_reference.py` checks that durablewrite matches
  it wherever a plain file is written, and differs only as this guide says
  elsewhere. Under the tracer both libraries make the same fsync, rename,
  directory fsync sequence.

## Upgrading from 0.2

Code that worked with 0.2.0 keeps working, with these differences:

- `fsync="full"` now uses `MOVEFILE_WRITE_THROUGH` on Windows and `F_FULLFSYNC`
  on macOS.
- Arguments are checked when the writer is called rather than when the `with`
  block is entered, and more of them are checked: `bytes` paths, paths with a
  NUL, `permissions` outside `0..0o7777`, unknown encodings, invalid `newline`
  values, a `retry` that is not a `RetryPolicy`.
- `RetryPolicy` refuses non-integer attempts and delays or multipliers that are
  NaN, infinite or of the wrong type; `cleanup_temp_files` refuses a NaN or
  infinite age and a non-finite `now`.
- `cleanup_temp_files` removes read-only temp files on Windows.
- Error messages no longer repeat the refused value (the command line quotes at
  most 40 characters of it).
- `atomic_write` is typed per mode: `IO[str]` for `"w"`, `IO[bytes]` for `"wb"`.
- The `dev` extra is gone; contributors use `requirements-dev.txt`.

## Sources

Fetched on 2026-10-16.

1. Python documentation, `os.replace` and `os.fsync`:
   https://docs.python.org/3/library/os.html
2. Linux `fsync(2)` manual page: https://man7.org/linux/man-pages/man2/fsync.2.html
3. Jeff Moyer, "Ensuring data reaches disk", LWN.net, 2011:
   https://lwn.net/Articles/457667/
4. Linux kernel documentation, ext4 mount options (`auto_da_alloc`):
   https://docs.kernel.org/admin-guide/ext4.html
5. POSIX.1-2024, `rename`:
   https://pubs.opengroup.org/onlinepubs/9799919799/functions/rename.html
6. Microsoft, `MoveFileExW`:
   https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw
7. Microsoft, `FlushFileBuffers`:
   https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers
8. Apple, `fsync(2)` manual page (`F_FULLFSYNC`):
   https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/fsync.2.html
9. Microsoft, `_commit`:
   https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/commit
10. Microsoft, `CreateFileW` (`FILE_SHARE_DELETE`):
    https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
11. Microsoft, `ReplaceFileW`:
    https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew
12. Linux `rename(2)` manual page: https://man7.org/linux/man-pages/man2/rename.2.html
13. Linux `link(2)` manual page: https://man7.org/linux/man-pages/man2/link.2.html
