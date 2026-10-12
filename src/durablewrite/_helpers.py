"""One-shot helpers for text, bytes and JSON built on :func:`atomic_write`."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from ._atomic import atomic_write
from ._fs import StrPath
from ._options import DEFAULT_RETRY, FsyncLevel, RetryPolicy


def write_text_atomic(
    path: StrPath,
    text: str,
    encoding: str = "utf-8",
    *,
    newline: str | None = None,
    durable: bool = True,
    fsync_dir: bool = True,
    fsync: FsyncLevel | None = None,
    overwrite: bool = True,
    preserve_mode: bool = True,
    permissions: int | None = None,
    preserve_owner: bool = False,
    follow_symlinks: bool = True,
    retry: RetryPolicy = DEFAULT_RETRY,
) -> None:
    """Atomically replace ``path`` with ``text``.

    Keyword arguments have the meaning documented on :func:`atomic_write`.
    """
    with atomic_write(
        path,
        "w",
        encoding=encoding,
        newline=newline,
        durable=durable,
        fsync_dir=fsync_dir,
        fsync=fsync,
        overwrite=overwrite,
        preserve_mode=preserve_mode,
        permissions=permissions,
        preserve_owner=preserve_owner,
        follow_symlinks=follow_symlinks,
        retry=retry,
    ) as f:
        f.write(text)


def write_bytes_atomic(
    path: StrPath,
    data: bytes,
    *,
    durable: bool = True,
    fsync_dir: bool = True,
    fsync: FsyncLevel | None = None,
    overwrite: bool = True,
    preserve_mode: bool = True,
    permissions: int | None = None,
    preserve_owner: bool = False,
    follow_symlinks: bool = True,
    retry: RetryPolicy = DEFAULT_RETRY,
) -> None:
    """Atomically replace ``path`` with ``data``.

    Keyword arguments have the meaning documented on :func:`atomic_write`.
    """
    with atomic_write(
        path,
        "wb",
        durable=durable,
        fsync_dir=fsync_dir,
        fsync=fsync,
        overwrite=overwrite,
        preserve_mode=preserve_mode,
        permissions=permissions,
        preserve_owner=preserve_owner,
        follow_symlinks=follow_symlinks,
        retry=retry,
    ) as f:
        f.write(data)


def write_json_atomic(
    path: StrPath,
    obj: Any,
    *,
    indent: int | str | None = 2,
    sort_keys: bool = False,
    ensure_ascii: bool = False,
    default: Callable[[Any], Any] | None = None,
    allow_nan: bool = False,
    fsync: FsyncLevel = "full",
    overwrite: bool = True,
    preserve_mode: bool = True,
    permissions: int | None = None,
    preserve_owner: bool = False,
    follow_symlinks: bool = True,
    retry: RetryPolicy = DEFAULT_RETRY,
) -> None:
    """Atomically replace ``path`` with ``obj`` encoded as UTF-8 JSON.

    The value is serialised before any file is touched, so an object that
    cannot be encoded raises :class:`TypeError` (or :class:`ValueError` for a
    circular reference) and leaves both the target and the directory unchanged.
    ``NaN`` and infinities are not valid JSON (RFC 8259), so they raise
    :class:`ValueError` unless ``allow_nan=True``.
    The output ends with a single ``\n`` and uses ``\n`` line endings on every
    platform. ``indent``, ``sort_keys``, ``ensure_ascii``, ``default`` and ``allow_nan`` are
    passed to :func:`json.dumps`; the rest is documented on :func:`atomic_write`.
    """
    text = json.dumps(
        obj,
        indent=indent,
        sort_keys=sort_keys,
        ensure_ascii=ensure_ascii,
        default=default,
        allow_nan=allow_nan,
    )
    write_bytes_atomic(
        path,
        (text + "\n").encode("utf-8"),
        fsync=fsync,
        overwrite=overwrite,
        preserve_mode=preserve_mode,
        permissions=permissions,
        preserve_owner=preserve_owner,
        follow_symlinks=follow_symlinks,
        retry=retry,
    )
