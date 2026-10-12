"""Low-level filesystem steps: temp file creation, metadata, fsync, cleanup."""

from __future__ import annotations

import errno
import os
import secrets
import stat
import sys
from contextlib import suppress
from typing import Union

StrPath = Union[str, "os.PathLike[str]"]

TEMP_SUFFIX = ".dwtmp"
# Keeps ".<base>.<8 hex>.dwtmp" under the 255-byte name limit even for 4-byte UTF-8.
_MAX_BASE_CHARS = 48
_CREATE_FLAGS = (
    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
)


def temp_prefix(base: str) -> str:
    """Return the name prefix shared by every temp file for target ``base``."""
    return f".{base[:_MAX_BASE_CHARS]}."


def resolve_target(path: str, follow_symlinks: bool) -> str:
    """Return the path whose directory entry the rename will replace."""
    if not path:
        raise ValueError("path must not be empty")
    if follow_symlinks and os.path.islink(path):
        return os.path.realpath(path)
    return path


def stat_or_none(path: str) -> os.stat_result | None:
    """Stat ``path`` (following links), or return None when it does not exist."""
    try:
        return os.stat(path)
    except FileNotFoundError:
        return None


def create_temp(directory: str, base: str) -> tuple[int, str]:
    """Create an empty temp file next to the target and return ``(fd, path)``.

    Mode ``0o666`` with ``O_EXCL`` lets the process umask apply exactly as it
    does for ``open()``; ``tempfile.mkstemp`` would force ``0o600``.
    """
    prefix = temp_prefix(base)
    for _ in range(100):
        path = os.path.join(directory, f"{prefix}{secrets.token_hex(4)}{TEMP_SUFFIX}")
        try:
            return os.open(path, _CREATE_FLAGS, 0o666), path
        except FileExistsError:
            continue
    raise FileExistsError(errno.EEXIST, "could not pick a free temp file name", directory)


def apply_metadata(
    fd: int,
    tmp: str,
    existing: os.stat_result | None,
    *,
    preserve_mode: bool,
    permissions: int | None,
    preserve_owner: bool,
) -> None:
    """Give the temp file the ownership and permission bits it should end with."""
    if sys.platform != "win32" and preserve_owner and existing is not None:
        # chown before chmod: chown clears setuid/setgid bits on Linux.
        os.fchown(fd, existing.st_uid, existing.st_gid)
    if permissions is not None:
        os.chmod(tmp, permissions)
    elif preserve_mode and existing is not None and os.name != "nt":
        os.chmod(tmp, stat.S_IMODE(existing.st_mode))


def fsync_directory(directory: str) -> None:
    """Flush the directory entry so a completed rename survives power loss.

    Windows offers no way to fsync a directory through the C runtime, so this
    is a documented no-op there.
    """
    if os.name == "nt":
        return
    fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def remove_quietly(path: str) -> bool:
    """Best-effort removal used on error paths; never masks the original error."""
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return False
    except PermissionError:
        if os.name != "nt":
            return False
        # A read-only attribute blocks deletion on Windows; clear it and retry once.
        with suppress(OSError):
            os.chmod(path, stat.S_IWRITE)
            os.remove(path)
            return True
        return False
    except OSError:
        return False
