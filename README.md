# durablewrite

Durable, cross-platform atomic file writes. Write to a temp file in the same
directory, flush and fsync it, move it onto the target with `os.replace`, then
fsync the directory. A reader never sees a half-written file, and a crash leaves
the previous version intact.

## Install

```
pip install durablewrite
```

## Usage

```python
from durablewrite import atomic_write, write_text_atomic, write_bytes_atomic

# One-shot helpers.
write_text_atomic("config.json", '{"ready": true}')
write_bytes_atomic("snapshot.bin", b"\x00\x01\x02")

# Context manager for streamed writes.
with atomic_write("report.txt") as f:
    for line in rows:
        f.write(line + "\n")
# report.txt now holds the full content, or (on a crash) the old content.

# Binary mode.
with atomic_write("image.png", "wb") as f:
    f.write(data)
```

Text mode defaults to UTF-8. Writes are durable by default (the temp file is
fsynced before the rename and the directory is fsynced after). Turn either off
for speed when durability is not required:

```python
write_text_atomic("cache.txt", payload, durable=False, fsync_dir=False)
```

`os.replace` is atomic only within a single volume, so keep the target on the
same filesystem as its directory (the default, since the temp file is created
there). Directory fsync is a no-op on Windows, which exposes no fsyncable
directory handle.

## Why

Writing a file in place can corrupt it: a crash, a full disk or a second reader
can catch the file half-written. The safe pattern is well known (temp file in
the same directory, fsync, `os.replace`, fsync the directory), but it is fiddly
to get right on every platform and easy to get subtly wrong.

The options that existed each fall short:

- `atomicwrites`, the de-facto package, was **archived by its author in 2022**
  and takes no fixes.
- `boltons.fileutils.atomic_save` has **no Windows support**.
- The `atomicfile` and `atomicwrite` packages on PyPI are **abandoned** (last
  releases in 2020 and 2015) and neither is typed.
- `safewrite` is minimal and obscure.

`durablewrite` is a small, typed, zero-dependency (standard library only) take
that does the full dance (temp-same-dir, file and directory fsync, `os.replace`)
and is correct on both Windows and POSIX.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
