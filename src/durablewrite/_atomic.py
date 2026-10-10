"""Atomic, durable file writes built on a same-directory temp file plus os.replace."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from typing import IO, Any, Union

StrPath = Union[str, "os.PathLike[str]"]

_VALID_MODES = ("w", "wb")


def _silent_remove(path: str) -> None:
    """Remove a leftover temp file, ignoring the case where it is already gone."""
    with suppress(FileNotFoundError):
        os.remove(path)


def _fsync_dir(directory: str) -> None:
    """Flush the directory entry so a rename survives a crash.

    Windows exposes no fsyncable directory handle (opening a directory for
    os.fsync fails), so the call is a documented no-op there.
    """
    if os.name == "nt":
        return
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def atomic_write(
    path: StrPath,
    mode: str = "w",
    *,
    encoding: str | None = None,
    newline: str | None = None,
    durable: bool = True,
    fsync_dir: bool = True,
) -> Iterator[IO[Any]]:
    """Write to ``path`` so readers only ever see the old file or the complete new one.

    The data is written to a temp file in the same directory, flushed and (by
    default) fsynced, then moved onto ``path`` with ``os.replace``, which is
    atomic on the same volume on both Windows and POSIX. If the block raises,
    ``path`` is left untouched and the temp file is removed.

    ``mode`` is ``"w"`` (text) or ``"wb"`` (bytes). Set ``durable=False`` to skip
    the file fsync, and ``fsync_dir=False`` to skip flushing the directory entry.
    """
    if mode not in _VALID_MODES:
        raise ValueError(f"mode must be one of {_VALID_MODES!r}, got {mode!r}")
    binary = mode == "wb"
    if binary and encoding is not None:
        raise ValueError("encoding is not allowed in binary mode")
    if binary and newline is not None:
        raise ValueError("newline is not allowed in binary mode")
    if not binary and encoding is None:
        encoding = "utf-8"

    target = os.fspath(path)
    directory = os.path.dirname(os.path.abspath(target))
    base = os.path.basename(target) or "out"
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=f".{base}.", suffix=".tmp")

    replaced = False
    try:
        handle: IO[Any]
        if binary:
            handle = os.fdopen(fd, "wb")
        else:
            handle = os.fdopen(fd, "w", encoding=encoding, newline=newline)
        with handle as f:
            yield f
            f.flush()
            if durable:
                os.fsync(f.fileno())
        os.replace(tmp, target)
        replaced = True
        if fsync_dir:
            _fsync_dir(directory)
    finally:
        if not replaced:
            _silent_remove(tmp)


def write_text_atomic(
    path: StrPath,
    text: str,
    encoding: str = "utf-8",
    *,
    newline: str | None = None,
    durable: bool = True,
    fsync_dir: bool = True,
) -> None:
    """Atomically replace ``path`` with ``text`` (see :func:`atomic_write`)."""
    with atomic_write(
        path,
        "w",
        encoding=encoding,
        newline=newline,
        durable=durable,
        fsync_dir=fsync_dir,
    ) as f:
        f.write(text)


def write_bytes_atomic(
    path: StrPath,
    data: bytes,
    *,
    durable: bool = True,
    fsync_dir: bool = True,
) -> None:
    """Atomically replace ``path`` with ``data`` (see :func:`atomic_write`)."""
    with atomic_write(path, "wb", durable=durable, fsync_dir=fsync_dir) as f:
        f.write(data)
