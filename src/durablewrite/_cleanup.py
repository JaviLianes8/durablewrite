"""Removal of temp files left behind by writers that were killed mid-write."""

from __future__ import annotations

import os
import re
import time

from ._check import check_path, check_real
from ._fs import TEMP_SUFFIX, StrPath, temp_stem, try_remove

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
            writer keeps one open for longer than that. ``0`` removes every
            matching file whatever its time; pass it only when you know no
            writer is active.
        target: Restrict the cleanup to temp files of this one target file.
        now: The current time as a Unix timestamp; defaults to :func:`time.time`.

    Returns:
        The removed paths, sorted. Files that vanish concurrently, that are
        still held open (Windows refuses to delete them) or that cannot be
        removed for any other reason are skipped.

    Raises:
        TypeError: An argument has the wrong type (``bytes`` paths included).
        ValueError: ``older_than`` is negative or not finite, or ``now`` is
            not finite.
        OSError: ``directory`` cannot be listed (missing, not a directory).

    >>> import os, tempfile
    >>> with tempfile.TemporaryDirectory() as folder:
    ...     stale = os.path.join(folder, ".data.json.0123abcd.dwtmp")
    ...     open(stale, "wb").close()
    ...     removed = cleanup_temp_files(folder, older_than=0)
    ...     print([os.path.basename(p) for p in removed], os.listdir(folder))
    ['.data.json.0123abcd.dwtmp'] []
    """
    age = check_real("older_than", older_than)
    folder = check_path(directory)
    cutoff = (time.time() if now is None else check_real("now", now, minimum=None)) - age
    pattern = _TEMP_NAME
    if target is not None:
        stem = temp_stem(os.path.basename(check_path(target)))
        pattern = re.compile(r"^\." + re.escape(stem) + _TAIL, re.DOTALL)
    removed: list[str] = []
    with os.scandir(folder) as entries:
        for entry in entries:
            if not pattern.match(entry.name):
                continue
            try:
                if not entry.is_file(follow_symlinks=False):
                    continue
                # Zero means every match: file times can run ahead of time.time().
                if age > 0 and entry.stat(follow_symlinks=False).st_mtime > cutoff:
                    continue
            except OSError:
                continue
            if try_remove(entry.path, missing_ok=False):
                removed.append(entry.path)
    return sorted(removed)
