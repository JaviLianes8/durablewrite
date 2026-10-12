"""Low-level filesystem steps: temp file creation, metadata, fsync, removal."""

from __future__ import annotations

import errno
import hashlib
import os
import secrets
import stat
import sys
from typing import Union

StrPath = Union[str, "os.PathLike[str]"]

TEMP_SUFFIX = ".dwtmp"
# Keeps ".<stem>.<8 hex>.dwtmp" under the 255-byte name limit even for 4-byte UTF-8.
_MAX_STEM_CHARS = 48
_CREATE_FLAGS = (
    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_CLOEXEC", 0)
)


def temp_stem(base: str) -> str:
    """Return the part of a temp file name that identifies target ``base``.

    Short names are used as is. Longer ones keep a readable head plus a hash of
    the full name, so two long names never share temp files.
    """
    if len(base) <= _MAX_STEM_CHARS:
        return base
    digest = hashlib.sha256(base.encode("utf-8", "surrogatepass")).hexdigest()[:8]
    return f"{base[: _MAX_STEM_CHARS - 9]}~{digest}"


def resolve_target(path: str, follow_symlinks: bool) -> str:
    """Return the path whose directory entry the rename will replace."""
    if not path:
        raise ValueError("path must not be empty")
    if path.endswith(os.sep) or (os.altsep is not None and path.endswith(os.altsep)):
        raise ValueError(f"path must name a file, not end with a separator: {path!r}")
    if follow_symlinks and os.path.islink(path):
        return os.path.realpath(path)
    return path


def existing_stat(path: str, follow_symlinks: bool) -> os.stat_result | None:
    """Stat the file being replaced, or None for a new file.

    A symlink that is itself replaced (``follow_symlinks=False``) counts as a
    new file: the mode of whatever it points to is not inherited.
    """
    try:
        if not follow_symlinks and os.path.islink(path):
            return None
        return os.stat(path)
    except FileNotFoundError:
        return None


def create_temp(directory: str, base: str, private: bool) -> tuple[int, str]:
    """Create an empty temp file next to the target and return ``(fd, path)``.

    ``private`` creates it as ``0o600`` so content meant for a restrictive final
    mode is never readable by others while it is written. Otherwise ``0o666``
    lets the process umask apply exactly as it does for ``open()``.
    """
    prefix = f".{temp_stem(base)}."
    mode = 0o600 if private else 0o666
    for _ in range(100):
        path = os.path.join(directory, f"{prefix}{secrets.token_hex(4)}{TEMP_SUFFIX}")
        try:
            return os.open(path, _CREATE_FLAGS, mode), path
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


def try_remove(path: str) -> bool | None:
    """Remove ``path``: True if removed or gone, None if locked, False on other errors."""
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        return True
    except PermissionError as exc:
        if os.name != "nt":
            return False
        if getattr(exc, "winerror", None) in (32, 33):
            return None
        try:
            # A read-only attribute blocks deletion on Windows; clear it and retry once.
            os.chmod(path, stat.S_IWRITE)
            os.remove(path)
            return True
        except FileNotFoundError:
            return True
        except OSError:
            return None
    except OSError:
        return False
