"""The write protocol: temp file, flush, fsync, rename, directory fsync."""

from __future__ import annotations

import errno
import io
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from typing import IO, Any

from ._errors import DirectorySyncError
from ._fs import (
    apply_metadata,
    create_temp,
    existing_stat,
    fsync_directory,
    resolve_target,
    sync_fd,
)
from ._options import RetryPolicy
from ._replace import publish, remove_temp


@dataclass(frozen=True)
class Plan:
    """Checked arguments of one write; built by :func:`durablewrite.atomic_write`."""

    path: str
    binary: bool
    encoding: str | None
    newline: str | None
    sync_file: bool
    sync_dir: bool
    overwrite: bool
    preserve_mode: bool
    permissions: int | None
    preserve_owner: bool
    follow_symlinks: bool
    retry: RetryPolicy


def _open(fd: int, plan: Plan) -> IO[Any]:
    """Wrap ``fd``; the raw file owns it from the first call, so it is closed once."""
    raw = os.fdopen(fd, "wb")
    if plan.binary:
        return raw
    try:
        return io.TextIOWrapper(raw, encoding=plan.encoding or "utf-8", newline=plan.newline)
    except BaseException:
        raw.close()
        raise


def _refuse_special(target: str, follow_symlinks: bool) -> None:
    """FIFOs, devices and sockets are never swapped for a regular file."""
    try:
        info = os.stat(target) if follow_symlinks else os.lstat(target)
    except OSError:
        return
    if stat.S_ISDIR(info.st_mode):
        raise IsADirectoryError(errno.EISDIR, "target is a directory", target)
    if not (stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode)):
        raise OSError(errno.EINVAL, "target is not a regular file", target)


@contextmanager
def run(plan: Plan) -> Iterator[IO[Any]]:
    """Yield the temp file handle and publish it if the block exits normally."""
    # Pinned to an absolute path now: a chdir while the block runs must not move the
    # rename away from the directory that holds the temp file and gets fsynced.
    target = resolve_target(plan.path, plan.follow_symlinks)
    if not os.path.isabs(target):
        target = os.path.join(os.getcwd(), target)
    _refuse_special(target, plan.follow_symlinks)
    if not plan.overwrite and os.path.lexists(target):
        raise FileExistsError(errno.EEXIST, "target already exists", target)
    directory = os.path.dirname(target)
    existing = existing_stat(target, plan.follow_symlinks)
    private = plan.permissions is not None or (plan.preserve_mode and existing is not None)
    tmp: str | None = None
    fd = -1
    published = False
    try:
        fd, tmp = create_temp(directory, os.path.basename(target), private)
        handle, fd = _open(fd, plan), -1
        with handle as f:
            yield f
            f.flush()
            apply_metadata(
                f.fileno(),
                tmp,
                existing,
                preserve_mode=plan.preserve_mode,
                permissions=plan.permissions,
                preserve_owner=plan.preserve_owner,
            )
            if plan.sync_file:
                sync_fd(f.fileno())
        publish(
            tmp, target, overwrite=plan.overwrite, retry=plan.retry, write_through=plan.sync_dir
        )
        published = True
    finally:
        if fd >= 0:  # interrupted between creating the temp file and wrapping it
            with suppress(OSError):
                os.close(fd)
        if tmp is not None and not published:
            remove_temp(tmp, plan.retry)
    if plan.sync_dir:
        try:
            fsync_directory(directory)
        except OSError as exc:
            raise DirectorySyncError(
                exc.errno,
                f"file replaced, but its directory was not synced: {exc.strerror}",
                directory,
            ) from exc
