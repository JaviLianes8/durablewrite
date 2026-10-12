"""Publishing the finished temp file under the target name, with bounded retry."""

from __future__ import annotations

import errno
import os
import stat
from contextlib import suppress

from ._errors import SharingViolationError
from ._options import RetryPolicy

# ERROR_ACCESS_DENIED, ERROR_SHARING_VIOLATION, ERROR_LOCK_VIOLATION.
_TRANSIENT_WINERRORS = frozenset({5, 32, 33})


def _is_read_only(path: str) -> bool:
    try:
        attributes = getattr(os.stat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_READONLY)


def _is_transient(exc: OSError, target: str) -> bool:
    """True for a Windows lock that may clear by itself, never for a real denial."""
    if os.name != "nt" or not isinstance(exc, PermissionError):
        return False
    if getattr(exc, "winerror", None) not in _TRANSIENT_WINERRORS:
        return False
    return not _is_read_only(target) and not os.path.isdir(target)


def _create_new(tmp: str, target: str) -> None:
    """Move ``tmp`` to ``target`` only if ``target`` does not exist, atomically.

    POSIX ``rename`` always overwrites, so a hard link is used instead: ``link``
    fails with ``EEXIST`` if the name is taken. On Windows ``MoveFileExW``
    without ``MOVEFILE_REPLACE_EXISTING`` fails the same way.
    """
    if os.name == "nt":
        os.rename(tmp, target)
        return
    os.link(tmp, target)
    with suppress(FileNotFoundError):
        os.remove(tmp)


def publish(tmp: str, target: str, *, overwrite: bool, retry: RetryPolicy) -> None:
    """Rename ``tmp`` onto ``target``, retrying transient Windows locks only."""
    move = os.replace if overwrite else _create_new
    delays = retry.delays()
    attempt = 1
    while True:
        try:
            move(tmp, target)
            return
        except OSError as exc:
            if not _is_transient(exc, target):
                raise
            delay = next(delays, None)
            if delay is None:
                error = SharingViolationError(
                    errno.EACCES,
                    f"target stayed locked by another process after {attempt} attempts",
                    target,
                )
                error.attempts = attempt
                raise error from exc
            retry.sleep(delay)
            attempt += 1
