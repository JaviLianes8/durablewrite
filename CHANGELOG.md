# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-16

The public API is now stable: the twelve names in `durablewrite.__all__`, their
parameters, defaults and error types, the temp file naming scheme that
`cleanup_temp_files` relies on, and the command line options and exit statuses
follow Semantic Versioning from here on.

### Changed

- `fsync="full"` (the default) on Windows renames with `MoveFileExW` and
  `MOVEFILE_WRITE_THROUGH`, so the rename itself is written to disk before the
  call returns; `"file"` and `"none"` keep plain `os.replace`.
- On macOS every flush uses `F_FULLFSYNC`, falling back to `fsync` where the
  filesystem refuses it.
- All arguments are checked when a writer is called, before any file is
  touched, instead of when the `with` block is entered.
- Error messages no longer repeat the refused value; the command line quotes at
  most 40 characters of the values it checks and cuts every error or warning
  message after its prefix to 120 characters, keeping its start and its end.
- On/off options (`overwrite`, `durable`, `fsync_dir`, `preserve_mode`,
  `preserve_owner`, `follow_symlinks`) accept only `True` or `False`, and a `mode`
  or `fsync` that is not a string raises `TypeError`: before, any value was taken
  by truthiness, so `overwrite="no"` overwrote the file.
- `atomic_write` is typed per mode: `IO[str]` for `"w"`, `IO[bytes]` for `"wb"`
  (`IO[Any]` only for a mode that is not a literal).
- `cleanup_temp_files` also removes read-only temp files on Windows, and
  `older_than=0` removes every matching temp file whatever its time (on Windows
  with Python 3.10 to 3.12 a file just written could look newer than the clock
  and be skipped).
- Errors raised before the block runs name the path as it was given (for a
  followed symlink, the file it points to); errors from
  the rename name the target as an absolute path, since a relative target is
  pinned to the working directory when the write starts.
- A `retry` that is not a `RetryPolicy` raises `TypeError` (0.2.0 raised
  `AttributeError` and left a temp file).
- The `dev` extra is replaced by `requirements-dev.txt`.

### Fixed

- `cleanup_temp_files(older_than=float("nan"))` removed every temp file,
  including those of running writers; a NaN or infinite age, a non-finite `now`
  and non-number ages now raise.
- `RetryPolicy` accepted NaN and infinite delays, which made a blocked write
  fail with an unrelated error and leave its temp file behind, non-integer or
  `bool` attempts and a `sleep` that is not callable; these now raise
  `TypeError` or `ValueError`.
- A FIFO, device or socket target was silently replaced by a regular file
  (`durablewrite /dev/null` as root replaced the device; `--append` on a FIFO
  hung); it now raises `OSError` with `EINVAL`.
- Permission bits were set on the temp file by name; on POSIX they now go
  through the descriptor (`fchmod`), so a temp name swapped for a symlink cannot
  redirect them.
- A text wrapper that failed to build closed the file descriptor twice and hid
  its own error behind `EBADF`; codecs that are not text encodings (`hex`) are now
  refused up front with `LookupError`.
- An interrupt between creating the temp file and wrapping it left the
  descriptor open, so on Windows the temp file could not be removed.
- `--json` refused valid JSON with integers longer than 4300 digits.
- On Windows a name with `:` wrote to an alternate data stream and left an empty
  file behind; it now raises `ValueError`.
- `RetryPolicy` accepted delays so long that `time.sleep` overflowed; delays are
  now limited to one day.
- `bytes` paths, paths containing NUL, `permissions` outside `0..0o7777`,
  `permissions=True`, unknown encodings and invalid `newline` values failed late
  or with unrelated errors; they now raise `TypeError`, `ValueError` or `LookupError` up front.

### Added

- Ground truth in the test suite: kill-at-every-call tests on every platform, a
  Linux system call tracer, 120 scenarios recorded from `atomicwrites` 1.4.1 on
  Windows and Linux, and a manifest of the cited OS documentation.
- Doctests for every public name, seeded fuzz tests and linear-time checks.

## [0.2.0] - 2026-10-14

### Added

- `write_json_atomic(path, obj, ...)`: serialises before touching the disk and
  writes UTF-8 JSON with a trailing newline and LF line endings. `NaN` and
  infinities are refused unless `allow_nan=True`.
- `fsync="none" | "file" | "full"` on every writer, with the `FsyncLevel` type.
  The `durable` and `fsync_dir` flags keep working.
- `overwrite=False`: atomic create-if-absent (`link` on POSIX, `MoveFileExW`
  without the replace flag on Windows).
- `preserve_mode` (default on), `permissions` and `preserve_owner` options.
- `follow_symlinks` (default on): writing through a symlink updates the file it
  points to and keeps the link.
- `RetryPolicy`, `DEFAULT_RETRY` and `NO_RETRY`: bounded backoff when a Windows
  sharing or lock violation blocks the rename.
- `DurableWriteError` (an `OSError`), `SharingViolationError` (a
  `PermissionError`) and `DirectorySyncError` (the file was replaced but its
  directory could not be fsynced).
- `cleanup_temp_files(directory, older_than=..., target=...)` for temp files
  left by killed writers.
- `durablewrite` command line tool (also `python -m durablewrite`): writes
  standard input to a file atomically, with `--append`, `--json`, `--fsync`,
  `--no-overwrite`, `--permissions`, `--no-follow-symlinks` and `--attempts`.
  Exit status 1 on errors, 3 when the file was replaced but not fully synced.
- `GUIDE.md` with the write protocol, per-platform guarantees and sources.

### Changed

- Temp files are named `.<name>.<8 hex digits>.dwtmp` so they can be cleaned up
  safely.
- Writing through a symlink no longer replaces the link with a regular file
  (pass `follow_symlinks=False` for the old behaviour).

### Fixed

- New files were created with mode `0600` and replaced files lost their mode;
  new files now honour the umask like `open()` and replaced files keep their
  permission bits.
- Very long file names no longer overflow the name limit when the temp name is
  built.
- Writing to an existing directory raises `IsADirectoryError` before any temp
  file is created, and a path ending with a separator raises `ValueError`.
- When the final mode is restricted (explicit `permissions` or a replaced
  private file) the temp file is `0600` while it is written.
- On Windows, removal of a temp file that is briefly locked is retried.

## [0.1.0] - 2026-10-11 (not published)

### Added

- `atomic_write(path, mode, *, encoding, newline, durable, fsync_dir)` context
  manager: writes to a temp file in the target directory, flushes and fsyncs it,
  then moves it onto the target with `os.replace` and fsyncs the directory.
- `write_text_atomic(path, text, encoding, *, newline, durable, fsync_dir)` and
  `write_bytes_atomic(path, data, *, durable, fsync_dir)` one-shot helpers.
- Durable by default (file and directory fsync), both switchable off.
- Correct on Windows and POSIX; typed, zero runtime dependencies.
