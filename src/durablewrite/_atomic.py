"""The public context manager and the argument checks it runs before any I/O."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import IO, Any, Literal, overload

from ._check import check_flag, check_permissions, check_target, check_text_options
from ._fs import StrPath
from ._options import DEFAULT_RETRY, FsyncLevel, RetryPolicy, resolve_fsync
from ._write import Plan, run


def build_plan(
    path: StrPath,
    mode: str,
    *,
    encoding: str | None,
    newline: str | None,
    sync: tuple[bool, bool],
    overwrite: bool,
    preserve_mode: bool,
    permissions: int | None,
    preserve_owner: bool,
    follow_symlinks: bool,
    retry: RetryPolicy,
) -> Plan:
    """Check every argument of a write and return them as a :class:`Plan`."""
    if not isinstance(mode, str):
        raise TypeError("mode must be a str")
    if mode not in ("w", "wb"):
        raise ValueError("mode must be 'w' or 'wb'")
    binary = mode == "wb"
    check_text_options(binary, encoding, newline)
    if not isinstance(retry, RetryPolicy):
        raise TypeError("retry must be a RetryPolicy")
    return Plan(
        path=check_target(path),
        binary=binary,
        encoding=encoding,
        newline=newline,
        sync_file=sync[0],
        sync_dir=sync[1],
        overwrite=check_flag("overwrite", overwrite),
        preserve_mode=check_flag("preserve_mode", preserve_mode),
        permissions=check_permissions(permissions),
        preserve_owner=check_flag("preserve_owner", preserve_owner),
        follow_symlinks=check_flag("follow_symlinks", follow_symlinks),
        retry=retry,
    )


@overload
def atomic_write(
    path: StrPath,
    mode: Literal["w"] = ...,
    *,
    encoding: str | None = ...,
    newline: str | None = ...,
    durable: bool = ...,
    fsync_dir: bool = ...,
    fsync: FsyncLevel | None = ...,
    overwrite: bool = ...,
    preserve_mode: bool = ...,
    permissions: int | None = ...,
    preserve_owner: bool = ...,
    follow_symlinks: bool = ...,
    retry: RetryPolicy = ...,
) -> AbstractContextManager[IO[str]]: ...
@overload
def atomic_write(
    path: StrPath,
    mode: Literal["wb"],
    *,
    encoding: None = ...,
    newline: None = ...,
    durable: bool = ...,
    fsync_dir: bool = ...,
    fsync: FsyncLevel | None = ...,
    overwrite: bool = ...,
    preserve_mode: bool = ...,
    permissions: int | None = ...,
    preserve_owner: bool = ...,
    follow_symlinks: bool = ...,
    retry: RetryPolicy = ...,
) -> AbstractContextManager[IO[bytes]]: ...
@overload
def atomic_write(
    path: StrPath,
    mode: str,
    *,
    encoding: str | None = ...,
    newline: str | None = ...,
    durable: bool = ...,
    fsync_dir: bool = ...,
    fsync: FsyncLevel | None = ...,
    overwrite: bool = ...,
    preserve_mode: bool = ...,
    permissions: int | None = ...,
    preserve_owner: bool = ...,
    follow_symlinks: bool = ...,
    retry: RetryPolicy = ...,
) -> AbstractContextManager[IO[Any]]: ...
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
) -> AbstractContextManager[IO[Any]]:
    """Write to ``path`` so readers only ever see the old file or the complete new one.

    The block writes to a temp file in the target's own directory. When it exits
    normally the data is flushed, synced as ``fsync`` asks and renamed onto
    ``path``; if it raises, ``path`` is untouched and the temp file removed.
    Arguments are checked when this is called, before any file is touched.
    Closing the handle inside the block discards the write with ValueError.

    >>> import os, tempfile
    >>> with tempfile.TemporaryDirectory() as folder:
    ...     path = os.path.join(folder, "notes.txt")
    ...     with atomic_write(path) as f:
    ...         _ = f.write("hello")
    ...     print(open(path, encoding="utf-8").read())
    hello

    Args:
        path: The file to create or replace (``str`` or ``os.PathLike[str]``).
        mode: ``"w"`` for text (UTF-8 unless ``encoding`` is given) or ``"wb"``.
        encoding, newline: As for :func:`open`; text mode only.
        durable, fsync_dir: Legacy flags for the file and directory sync, used
            only when ``fsync`` is None. Both default to True, meaning ``"full"``.
        fsync: ``"none"``, ``"file"`` or ``"full"`` (see :data:`FsyncLevel`).
        overwrite: When False, publish only if nothing exists at ``path`` and
            raise :class:`FileExistsError` otherwise, atomically.
        preserve_mode: Copy the permission bits of the replaced file (POSIX).
            New files get ``0o666`` minus the umask, as with :func:`open`.
        permissions: Explicit bits from 0 to ``0o7777``; wins over
            ``preserve_mode``. On Windows only the read-only flag is affected.
        preserve_owner: Copy uid and gid of the replaced file (POSIX only).
        follow_symlinks: Write through a symlink and keep it (default), or
            replace the link itself.
        retry: How long to retry a rename blocked by a Windows lock.

    Raises:
        TypeError: ``path`` is bytes, an on/off option is not a bool, or another
            argument has the wrong type.
        ValueError: A bad ``mode``, ``fsync``, ``newline`` or ``permissions``,
            or a ``path`` that is empty, contains NUL, ends with a separator or
            (on Windows) names an alternate data stream.
        LookupError: An unknown ``encoding`` or one that is not a text encoding.
        IsADirectoryError: ``path`` is a directory.
        OSError: ``path`` is a FIFO, device or socket (``errno.EINVAL``).
        FileExistsError: ``overwrite`` is False and ``path`` exists.
        SharingViolationError: The rename stayed blocked for the whole retry budget.
        DirectorySyncError: The file was replaced, but the directory sync failed.
    """
    plan = build_plan(
        path,
        mode,
        encoding=encoding,
        newline=newline,
        sync=resolve_fsync(fsync, durable, fsync_dir),
        overwrite=overwrite,
        preserve_mode=preserve_mode,
        permissions=permissions,
        preserve_owner=preserve_owner,
        follow_symlinks=follow_symlinks,
        retry=retry,
    )
    return run(plan)
