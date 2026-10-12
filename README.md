# durablewrite

Durable, cross-platform atomic file writes for Python. Data goes to a temp file
in the same directory, is flushed and fsynced, then moved onto the target with
`os.replace`, and the directory is fsynced. A reader never sees a half-written
file, and a crash leaves either the previous version or the complete new one.

Typed, standard library only, Python 3.10+, Windows and POSIX.

## Install

```
pip install durablewrite
```

## Usage

```python
from durablewrite import atomic_write, write_bytes_atomic, write_json_atomic, write_text_atomic

# One-shot helpers.
write_text_atomic("notes.txt", "hello\n")
write_bytes_atomic("snapshot.bin", b"\x00\x01\x02")
write_json_atomic("config.json", {"ready": True})  # serialised before any file is touched

# Stream into a file: it is replaced only if the block finishes without an error.
with atomic_write("report.csv") as f:
    for row in rows:
        f.write(row + "\n")

with atomic_write("image.png", "wb") as f:
    f.write(data)
```

### Options (on every writer)

| Option | Default | Meaning |
| --- | --- | --- |
| `fsync` | `"full"` | `"none"`, `"file"` (fsync the data) or `"full"` (data and directory) |
| `overwrite` | `True` | `False`: create only if absent, atomically, else `FileExistsError` |
| `preserve_mode` | `True` | keep the permission bits of the file being replaced (POSIX) |
| `permissions` | `None` | explicit permission bits, e.g. `0o600` |
| `preserve_owner` | `False` | keep uid and gid of the replaced file (POSIX) |
| `follow_symlinks` | `True` | write through a symlink and keep it, or replace the link itself |
| `retry` | `DEFAULT_RETRY` | bounded retry while Windows reports the target locked |

New files get `0o666` minus your umask, exactly like `open()`. When the final mode
comes from `permissions` or from the replaced file, the temp file is created as
`0o600`, so a secret is never readable by others while it is being written.

```python
from durablewrite import NO_RETRY, RetryPolicy, SharingViolationError, write_text_atomic

write_text_atomic("cache.txt", payload, fsync="none")  # atomic, not durable
write_text_atomic("token", secret, permissions=0o600, overwrite=False)

try:
    write_text_atomic("held.txt", "x", retry=RetryPolicy(max_attempts=20, max_delay=0.2))
except SharingViolationError as exc:  # a PermissionError; target untouched
    print("still locked after", exc.attempts, "attempts")
```

A writer that is killed mid-write cannot remove its temp file. Clean those up
at startup:

```python
from durablewrite import cleanup_temp_files

cleanup_temp_files("data/", older_than=3600)  # only *.dwtmp files written by durablewrite
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

Options: `--append`, `--json` (refuse invalid JSON), `--fsync {none,file,full}`,
`--no-overwrite`, `--permissions OCTAL`, `--no-follow-symlinks`,
`--attempts N`. Errors go to standard error with exit status 1, and TARGET is
left as it was. If TARGET was replaced but its directory could not be fsynced,
the exit status is 3. `python -m durablewrite` works too.

On Windows, redirecting TARGET into the command (`durablewrite f < f`) is refused,
because the shell keeps the redirected file open and that blocks the rename; pipe
it instead (`type f | durablewrite f`). Concurrent `--append` runs on one file may
lose each other's lines: each run is atomic, but they do not merge.

## Guarantees and limits

The short version (details and sources in [GUIDE.md](GUIDE.md)):

- **Atomic for readers and against process crashes** on local filesystems,
  Windows and POSIX. Exercised by a seeded test that kills a writer process at
  random moments and by a multi-process concurrent writer test.
- **Durable against power loss** on Linux with `fsync="full"`. On macOS, `fsync`
  does not flush the drive cache (`F_FULLFSYNC` is not issued). On Windows the
  file data is flushed but a directory cannot be fsynced.
- **Windows**: `os.replace` is `MoveFileExW`, not documented as atomic by
  Microsoft; tested on NTFS, not guaranteed on FAT or network shares. An open
  handle elsewhere blocks the rename; it is retried for about a second by
  default, then `SharingViolationError` is raised. While a rename is in flight,
  a concurrent `open()` of the target can fail with `PermissionError`; readers
  that poll should retry. A read-only target cannot be replaced on Windows.
- **After the rename**, a failing directory fsync raises `DirectorySyncError`:
  the new content is in place, but the rename may not survive a power loss.
- Replacing a file creates a new one: other hard links keep the old content,
  and extended attributes, ACLs and alternate data streams are not copied.

## Why

Writing a file in place can corrupt it: a crash, a full disk or a concurrent
reader can catch it half-written. The safe pattern (temp file in the same
directory, fsync, `os.replace`, fsync the directory) is well known but fiddly
to get right on every platform.

The options that existed each fall short:

- `atomicwrites`, the de-facto package, was **archived by its author in 2022**
  and takes no fixes.
- `boltons.fileutils.atomic_save` has **no Windows support**.
- The `atomicfile` and `atomicwrite` packages on PyPI are **abandoned** (last
  releases in 2020 and 2015) and neither is typed.
- `safewrite` is minimal and obscure.

`durablewrite` does the full sequence, keeps permissions, handles Windows
sharing violations, documents exactly what each platform guarantees, and ships
a command-line tool.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
