# durablewrite

Durable, cross-platform atomic file writes for Python. Data goes to a temp file
in the same directory, is flushed to disk, then renamed onto the target, and the
rename itself is made durable. A reader never sees a half-written file, and a
crash leaves either the previous version or the complete new one.

Typed, standard library only, Python 3.10+, Windows, Linux and macOS.

## Install

```
pip install durablewrite
```

## Quick start

```python
from durablewrite import atomic_write, write_bytes_atomic, write_json_atomic, write_text_atomic

# One-shot helpers.
write_text_atomic("notes.txt", "hello\n")
write_bytes_atomic("snapshot.bin", b"\x00\x01\x02")
write_json_atomic("config.json", {"ready": True})  # serialised before any file is touched

# Stream into a file: it is replaced only if the block finishes without an error.
rows = ["id,name", "1,ada", "2,grace"]
with atomic_write("report.csv", newline="") as f:
    for row in rows:
        f.write(row + "\n")

with atomic_write("image.png", "wb") as f:
    f.write(b"\x89PNG\r\n\x1a\n")
```

### Options (on every writer)

| Option | Default | Meaning |
| --- | --- | --- |
| `fsync` | `"full"` | `"none"`, `"file"` (flush the data) or `"full"` (data, then the rename) |
| `overwrite` | `True` | `False`: create only if absent, atomically, else `FileExistsError` |
| `preserve_mode` | `True` | keep the permission bits of the file being replaced (POSIX) |
| `permissions` | `None` | explicit permission bits from `0` to `0o7777`, e.g. `0o600` |
| `preserve_owner` | `False` | keep uid and gid of the replaced file (POSIX) |
| `follow_symlinks` | `True` | write through a symlink and keep it, or replace the link itself |
| `retry` | `DEFAULT_RETRY` | bounded retry while Windows reports the target locked |

Arguments are checked when the writer is called, before any file is touched: a
wrong type raises `TypeError` (on/off options take only `True` or `False`), a bad
value `ValueError`, an unknown encoding `LookupError`. New files get `0o666` minus your umask, exactly like `open()`.
When the final mode comes from `permissions` or from the replaced file, the temp
file is created as `0o600`, so a secret is never readable by others while it is
being written.

```python
from durablewrite import RetryPolicy, SharingViolationError, write_text_atomic

write_text_atomic("cache.txt", "warm", fsync="none")  # atomic, not durable
write_text_atomic("token", "s3cret", permissions=0o600, overwrite=False)

try:
    write_text_atomic("held.txt", "x", retry=RetryPolicy(max_attempts=20, max_delay=0.2))
except SharingViolationError as exc:  # a PermissionError; the target is untouched
    print("still locked after", exc.attempts, "attempts")
```

A writer that is killed mid-write cannot remove its temp file. Clean those up
at startup:

```python
from durablewrite import cleanup_temp_files

cleanup_temp_files(".", older_than=3600)  # only .<name>.<8 hex>.dwtmp files
```

## Command line

`durablewrite TARGET` writes standard input to TARGET atomically, like
`sponge`. TARGET is replaced only after the input ends.

```
sort names.txt | durablewrite names.txt
jq '.debug = true' config.json | durablewrite --json config.json
echo "one more line" | durablewrite --append notes.txt
printf 's3cret' | durablewrite --permissions 600 --no-overwrite token.txt
```

Options: `--append`, `--json` (refuse anything but strict JSON), `--fsync
{none,file,full}`, `--no-overwrite`, `--permissions OCTAL`,
`--no-follow-symlinks`, `--attempts N`. Errors go to standard error with exit
status 1, and TARGET is left as it was. If TARGET was replaced but its directory
could not be fsynced, the exit status is 3; an interrupted run exits 130.
`python -m durablewrite` works too.

## Guarantees and limits

The short version; the [guide](https://github.com/JaviLianes8/durablewrite/blob/main/GUIDE.md)
has the details and the sources.

- **Atomic for readers and against crashes of the writing process**, on local
  filesystems: POSIX documents `rename` as atomic; Microsoft does not say so for
  `MoveFileExW`, and on Windows this was observed on NTFS in our tests. Tested by killing a writer right before and right after every
  file system call it makes, on Windows and on Linux (where the calls are the
  real libc calls, traced with `LD_PRELOAD`), and by random kills mid-write.
- **Durable against power loss** with `fsync="full"`, as far as the operating
  system documents it: on Linux the data and then the directory are fsynced; on
  macOS `F_FULLFSYNC` is used so the drive flushes its own cache; on Windows the
  data is flushed (`FlushFileBuffers`) and the rename uses
  `MOVEFILE_WRITE_THROUGH`. No test can cut the power, so this rests on those
  documented calls.
- **Windows**: an open handle elsewhere blocks the rename; it is retried for
  about a second by default, then `SharingViolationError` is raised. A
  concurrent `open()` of the target can fail for a moment with
  `PermissionError` or, rarely, `FileNotFoundError` while a rename is in
  flight; readers that poll should retry. A read-only target cannot be replaced.
- **After the rename**, a failing directory fsync raises `DirectorySyncError`:
  the new content is in place, but the rename may not survive a power loss.
- Replacing a file creates a new one: other hard links keep the old content, and
  extended attributes, ACLs and alternate data streams are not copied.

## Why

Writing a file in place can corrupt it: a crash, a full disk or a concurrent
reader can catch it half-written. The safe sequence (temp file in the same
directory, flush, rename, make the rename durable) is well known but fiddly on
every platform.

- `atomicwrites` did the sequence well, but its repository is archived and its
  README marks it unmaintained; its last release, 1.4.1, dates from July 2022.
  It creates every file as `0o600` and replaces a symlink instead of writing
  through it.
- `boltons.fileutils.atomic_save` fsyncs the file but not the directory, and
  uses `ReplaceFileW` on Windows.
- `atomicfile` (last release 2020) and `atomicwrite` (2015) are no longer
  updated, and neither ships type information.

`durablewrite` runs the full sequence on every platform, keeps permissions,
retries Windows sharing violations, ships a command-line tool, and its test
suite checks it against the recorded behaviour of `atomicwrites` and against
traced system calls.

## Links

- [Guide](https://github.com/JaviLianes8/durablewrite/blob/main/GUIDE.md)
- [Changelog](https://github.com/JaviLianes8/durablewrite/blob/main/CHANGELOG.md)
- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/

## License

MIT. See [LICENSE](https://github.com/JaviLianes8/durablewrite/blob/main/LICENSE).
