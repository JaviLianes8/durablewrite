"""The write protocol: temp file, flush, fsync, rename, directory fsync."""

from __future__ import annotations

import errno
import os
from collections.abc import Iterator
from contextlib import contextmanager
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
    try:
        if plan.binary:
            return os.fdopen(fd, "wb")
        return os.fdopen(fd, "w", encoding=plan.encoding or "utf-8", newline=plan.newline)
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def run(plan: Plan) -> Iterator[IO[Any]]:
    """Yield the temp file handle and publish it if the block exits normally."""
    target = resolve_target(plan.path, plan.follow_symlinks)
    if os.path.isdir(target) and not os.path.islink(target):
        raise IsADirectoryError(errno.EISDIR, "target is a directory", target)
    if not plan.overwrite and os.path.lexists(target):
        raise FileExistsError(errno.EEXIST, "target already exists", target)
    directory = os.path.dirname(os.path.abspath(target))
    existing = existing_stat(target, plan.follow_symlinks)
    private = plan.permissions is not None or (plan.preserve_mode and existing is not None)
    tmp: str | None = None
    published = False
    try:
        fd, tmp = create_temp(directory, os.path.basename(target), private)
        with _open(fd, plan) as f:
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
        if tmp is not None and not published:
            remove_temp(tmp, plan.retry)
    if plan.sync_dir:
        try:
            fsync_directory(directory)
        except OSError as exc:
            raise DirectorySyncError(
                exc.errno, f"file replaced, but its directory was not synced: {exc}", directory
            ) from exc
