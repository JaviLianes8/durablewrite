# Improvements round: durablewrite

This round takes `durablewrite` from a correct but minimal context manager to a
complete atomic-write toolkit that is honest about what each platform does and
does not guarantee. Every promise below is backed by a test that runs on the real
filesystem: no mocked `os.replace`, no mocked `fsync`.

The public API grows additively. `atomic_write`, `write_text_atomic` and
`write_bytes_atomic` keep their signatures; new behaviour arrives through new
keyword arguments, new functions and a command-line tool.

## Ranked improvements

### 1. Correct permissions for new and replaced files (correctness, high)
`tempfile.mkstemp` creates files with mode `0600`, so 0.1.0 silently turned a
`0644` config or a `0755` script into a private, non-executable file on every
write. The temp file is now created with `O_CREAT | O_EXCL` and mode `0666`, so
the process umask applies exactly as it does for `open()`. When the target
already exists its permission bits are copied onto the temp file before the
rename (`preserve_mode=True`, the default). `permissions=0o600` sets explicit
bits, and `preserve_owner=True` copies uid and gid on POSIX.

### 2. Bounded retry on Windows sharing violations (robustness, high)
On Windows, `os.replace` is `MoveFileExW(MOVEFILE_REPLACE_EXISTING)`, which fails
with `ERROR_ACCESS_DENIED` or `ERROR_SHARING_VIOLATION` while another process
holds the target open without `FILE_SHARE_DELETE`. Python's own `open()` does not
pass that flag, and antivirus scanners and the search indexer open freshly
written files for a moment. A frozen `RetryPolicy` (attempts, initial delay,
multiplier, cap, injectable `sleep`) retries only those Windows error codes, never
a read-only target or a POSIX `EACCES`, and raises a typed
`SharingViolationError` (a `PermissionError`) when the budget runs out. The temp
file is always removed on that path.

### 3. Explicit fsync levels (clarity, high)
`fsync="none" | "file" | "full"` replaces the two loosely related booleans with
one named choice. `full` (the default) fsyncs the temp file before the rename and
the parent directory after it, which is what ext4 and XFS need for the rename to
survive power loss. The old `durable` and `fsync_dir` flags keep working. The
docs state plainly that Windows has no directory fsync and that macOS `fsync`
does not flush the drive cache.

### 4. JSON helper (convenience, high)
`write_json_atomic(path, obj, ...)` serialises first, so a value that cannot be
encoded raises before any file is created, then writes atomically with a trailing
newline. Defaults suit config files: `indent=2`, UTF-8, `ensure_ascii=False`.

### 5. Atomic create-if-absent (`overwrite=False`) (capability, medium)
Publishes the complete file only if nothing exists at the target, without a
check-then-act race: `os.link` on POSIX and a plain `MoveFileExW` without the
replace flag on Windows both fail atomically when the name is taken. Useful for
one-time initialisation and lock-free "first writer wins" files.

### 6. Documented symlink policy (correctness, medium)
Writing through a symlink now updates the file the link points to and keeps the
link (`follow_symlinks=True`), which is what dotfile managers expect. The temp
file is created next to the real target, so the rename never crosses a
filesystem. `follow_symlinks=False` replaces the link itself with a regular file.

### 7. Stale temp file cleanup (operations, medium)
A process killed mid-write cannot remove its temp file. Temp files now carry a
distinctive `.dwtmp` suffix and `cleanup_temp_files(directory, older_than=...)`
removes only those, only once they are old enough that no live writer can still
own them.

### 8. Typed errors and early validation (ergonomics, medium)
`DurableWriteError` is the base of errors the library raises itself and
subclasses `OSError`, so existing `except OSError` handlers keep working.
Writing to an existing directory raises `IsADirectoryError` before any temp file
exists. Long file names no longer overflow the 255-byte name limit when the temp
name is built.

### 9. A `sponge`-style CLI (tooling, medium)
`durablewrite TARGET` streams stdin into TARGET atomically, so
`sort data.txt | durablewrite data.txt` is safe. Flags cover `--append`,
`--json` (refuse to write invalid JSON), `--fsync`, `--no-overwrite`,
`--permissions` and `--attempts`. Errors go to stderr with exit status 1.

### 10. Guide with sources and real crash tests (trust, high)
A `GUIDE.md` explains the write protocol step by step with citations, and the
test suite proves the promise: a seeded kill-mid-write test that terminates a
writer process at random moments and checks the target is always a complete old
or complete new payload, a multi-process concurrent writer test, a held-open
reader test on Windows, and an end-to-end test that builds a wheel, installs it
into a throwaway virtual environment and drives the installed `durablewrite`
script.

## Out of scope this round

- `ReplaceFileW` on Windows. It preserves ACLs and attributes of the replaced
  file, but it is documented to fail half way (`ERROR_UNABLE_TO_MOVE_REPLACEMENT`)
  and requires the target to exist, so it would weaken the core promise.
- `F_FULLFSYNC` on macOS. Documented, not issued, because it cannot be exercised
  by the local test suite.
