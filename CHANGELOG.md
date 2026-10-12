# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0]

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

## [0.1.0]

### Added

- `atomic_write(path, mode, *, encoding, newline, durable, fsync_dir)` context
  manager: writes to a temp file in the target directory, flushes and fsyncs it,
  then moves it onto the target with `os.replace` and fsyncs the directory.
- `write_text_atomic(path, text, encoding, *, newline, durable, fsync_dir)` and
  `write_bytes_atomic(path, data, *, durable, fsync_dir)` one-shot helpers.
- Durable by default (file and directory fsync), both switchable off.
- Correct on Windows and POSIX; typed, zero runtime dependencies.
