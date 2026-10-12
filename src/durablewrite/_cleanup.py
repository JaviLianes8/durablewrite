"""Removal of temp files left behind by writers that were killed mid-write."""

from __future__ import annotations

import os
import re
import time

from ._fs import TEMP_SUFFIX, StrPath, temp_stem

_TAIL = r"\.[0-9a-f]{8}" + re.escape(TEMP_SUFFIX) + r"$"
_TEMP_NAME = re.compile(r"^\..+" + _TAIL, re.DOTALL)


def cleanup_temp_files(
    directory: StrPath,
    *,
    older_than: float = 3600.0,
    target: StrPath | None = None,
    now: float | None = None,
) -> list[str]:
    """Delete stale durablewrite temp files in ``directory`` and return their paths.

    A writer that is killed (or loses power) between creating its temp file and
    renaming it cannot clean up after itself. Such files are named
    ``.<target name>.<8 hex digits>.dwtmp``; only regular files matching that
    pattern are considered, so nothing else in the directory is ever touched.

    Args:
        directory: The directory to scan (not recursive).
        older_than: Minimum age in seconds, by modification time. The default of
            one hour leaves alone the temp files of running writers, unless a
            writer keeps one open for longer than that; pass ``0`` only when
            you know no writer is active.
        target: Restrict the cleanup to temp files of this one target file.
        now: The current time as a Unix timestamp; defaults to :func:`time.time`.

    Returns:
        The removed paths, sorted. Files that vanish concurrently or that are
        still held open (Windows refuses to delete them) are skipped.
    """
    if older_than < 0:
        raise ValueError("older_than must not be negative")
    cutoff = (time.time() if now is None else now) - older_than
    pattern = _TEMP_NAME
    if target is not None:
        stem = temp_stem(os.path.basename(os.fspath(target)))
        pattern = re.compile(r"^\." + re.escape(stem) + _TAIL, re.DOTALL)
    removed: list[str] = []
    with os.scandir(directory) as entries:
        for entry in entries:
            if not pattern.match(entry.name):
                continue
            try:
                if not entry.is_file(follow_symlinks=False):
                    continue
                if entry.stat(follow_symlinks=False).st_mtime > cutoff:
                    continue
                os.remove(entry.path)
            except (FileNotFoundError, PermissionError):
                continue
            removed.append(entry.path)
    return sorted(removed)
