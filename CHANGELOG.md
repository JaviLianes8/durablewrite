# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

### Added

- `atomic_write(path, mode, *, encoding, newline, durable, fsync_dir)` context
  manager: writes to a temp file in the target directory, flushes and fsyncs it,
  then moves it onto the target with `os.replace` and fsyncs the directory.
- `write_text_atomic(path, text, encoding, *, newline, durable, fsync_dir)` and
  `write_bytes_atomic(path, data, *, durable, fsync_dir)` one-shot helpers.
- Durable by default (file and directory fsync), both switchable off.
- Correct on Windows and POSIX; typed, zero runtime dependencies.
