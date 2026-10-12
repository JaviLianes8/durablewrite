"""The atomic write context manager: temp file, flush, fsync, rename, fsync dir."""

from __future__ import annotations

import errno
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import IO, Any

from ._errors import DirectorySyncError
from ._fs import (
    StrPath,
    apply_metadata,
    create_temp,
    existing_stat,
    fsync_directory,
    resolve_target,
)
from ._options import DEFAULT_RETRY, FsyncLevel, RetryPolicy, resolve_fsync
from ._replace import publish, remove_temp

_VALID_MODES = ("w", "wb")


def _check_mode(mode: str, encoding: str | None, newline: str | None) -> bool:
    if mode not in _VALID_MODES:
        raise ValueError(f"mode must be one of {_VALID_MODES!r}, got {mode!r}")
    binary = mode == "wb"
    if binary and encoding is not None:
        raise ValueError("encoding is not allowed in binary mode")
    if binary and newline is not None:
        raise ValueError("newline is not allowed in binary mode")
    return binary


@contextmanager
def atomic_write(
    path: StrPath,
    mode: str = "w",
    *,
    encoding: str | None = None,
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
) -> Iterator[IO[Any]]:
    """Write to ``path`` so readers only ever see the old file or the complete new one.

    The block writes to a temp file created in the target's own directory (so
    the final rename never crosses a filesystem). When the block exits normally
    the data is flushed, fsynced according to ``fsync``, and moved onto ``path``
    with ``os.replace``. If the block raises, ``path`` is untouched and the temp
    file is removed. Closing the handle inside the block is an error: the write
    is discarded and :class:`ValueError` is raised. While it is written, the
    temp file is only readable by its owner whenever the final mode comes from
    ``permissions`` or from the replaced file.

    Args:
        path: The file to create or replace.
        mode: ``"w"`` for text (UTF-8 unless ``encoding`` is given) or ``"wb"``.
        encoding: Text encoding; not allowed in binary mode.
        newline: Passed to the text wrapper as in :func:`open`.
        durable: Legacy flag for the file fsync; ignored when ``fsync`` is given.
        fsync_dir: Legacy flag for the directory fsync; ignored when ``fsync`` is given.
        fsync: ``"none"``, ``"file"`` or ``"full"`` (see :data:`FsyncLevel`).
            Defaults to the legacy flags, which mean ``"full"``.
        overwrite: When False, publish only if nothing exists at ``path`` and
            raise :class:`FileExistsError` otherwise, atomically.
        preserve_mode: Copy the permission bits of an existing target (POSIX).
            New files get ``0o666`` minus the umask, as with :func:`open`.
        permissions: Explicit permission bits; wins over ``preserve_mode``.
            On Windows only the read-only flag is affected.
        preserve_owner: Copy uid and gid of an existing target (POSIX only;
            usually needs privileges to change the uid). Ignored on Windows.
        follow_symlinks: When ``path`` is a symlink, replace the file it points
            to and keep the link (default), or replace the link itself.
        retry: How long to retry a rename blocked by a Windows lock.

    Raises:
        ValueError: An invalid ``mode``, ``fsync`` or argument combination, or
            a ``path`` that is empty or ends with a path separator.
        IsADirectoryError: ``path`` is an existing directory (or, when
            following symlinks, a link to one).
        FileExistsError: ``overwrite`` is False and ``path`` exists.
        SharingViolationError: The rename stayed blocked for the whole retry budget.
        DirectorySyncError: The file was replaced, but the directory fsync failed.
    """
    binary = _check_mode(mode, encoding, newline)
    sync_file, sync_dir = resolve_fsync(fsync, durable, fsync_dir)
    target = resolve_target(os.fspath(path), follow_symlinks)
    if os.path.isdir(target) and not os.path.islink(target):
        raise IsADirectoryError(errno.EISDIR, "target is a directory", target)
    if not overwrite and os.path.lexists(target):
        raise FileExistsError(errno.EEXIST, "target already exists", target)
    directory = os.path.dirname(os.path.abspath(target))
    existing = existing_stat(target, follow_symlinks)
    private = permissions is not None or (preserve_mode and existing is not None)
    tmp: str | None = None
    published = False
    try:
        fd, tmp = create_temp(directory, os.path.basename(target), private)
        try:
            if binary:
                handle: IO[Any] = os.fdopen(fd, "wb")
            else:
                handle = os.fdopen(fd, "w", encoding=encoding or "utf-8", newline=newline)
        except BaseException:
            os.close(fd)
            raise
        with handle as f:
            yield f
            f.flush()
            apply_metadata(
                f.fileno(),
                tmp,
                existing,
                preserve_mode=preserve_mode,
                permissions=permissions,
                preserve_owner=preserve_owner,
            )
            if sync_file:
                os.fsync(f.fileno())
        publish(tmp, target, overwrite=overwrite, retry=retry)
        published = True
    finally:
        if tmp is not None and not published:
            remove_temp(tmp, retry)
    if sync_dir:
        try:
            fsync_directory(directory)
        except OSError as exc:
            raise DirectorySyncError(
                exc.errno, f"file replaced, but its directory was not synced: {exc}", directory
            ) from exc
