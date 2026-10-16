"""Child process for the crash-point tests. Run as a script.

python _crashpoint.py SCENARIO TARGET LOG KILL_BEFORE KILL_AFTER

Wraps the file system calls durablewrite makes (os.open, os.fsync, os.replace,
os.rename, os.link, os.remove and the Windows MoveFileExW call), logs each one
to LOG, and kills this process with no cleanup at all right before or right
after call number KILL_BEFORE or KILL_AFTER (0 disables).
"""

from __future__ import annotations

import os
import signal
import sys
from collections.abc import Callable
from typing import Any

from durablewrite import _win, atomic_write

NEW = b"new content " * 4000
SCENARIOS: dict[str, dict[str, Any]] = {
    "replace": {"fsync": "full"},
    "replace-file": {"fsync": "file"},
    "replace-none": {"fsync": "none"},
    "create": {"fsync": "full"},
    "exclusive": {"fsync": "full", "overwrite": False},
}

_log_fd = -1
_count = 0
_limits = (0, 0)
_real_write = os.write


def _die() -> None:
    if os.name == "nt":
        os.kill(os.getpid(), signal.SIGTERM)  # TerminateProcess
    os.kill(os.getpid(), getattr(signal, "SIGKILL", signal.SIGTERM))


def _event(text: str) -> None:
    global _count
    _count += 1
    if _count == _limits[0]:
        _die()
    _real_write(_log_fd, (text + "\n").encode("utf-8", "surrogateescape"))


def _done() -> None:
    if _count == _limits[1]:
        _die()


def _short(path: str | int, root: str) -> str:
    text = str(path)
    try:
        name = os.path.relpath(text, root) if os.path.isabs(text) else text
    except ValueError:  # another drive on Windows
        name = text
    return "temp" if name.endswith(".dwtmp") else name


def _wrap(name: str, real: Callable[..., Any], root: str) -> Callable[..., Any]:
    def wrapper(*args: Any) -> Any:
        _event(f"{name} " + " ".join(_short(a, root) for a in args[:2] if not callable(a)))
        result = real(*args)
        _done()
        return result

    return wrapper


def _install(root: str) -> None:
    fds: dict[int, str] = {}
    real_open, real_fsync = os.open, os.fsync

    def open_(path: str, flags: int, mode: int = 0o777) -> int:
        _event(f"open {_short(path, root)}")
        fd = real_open(path, flags, mode)
        fds[fd] = _short(path, root)
        _done()
        return fd

    def fsync_(fd: int) -> None:
        _event(f"fsync {fds.get(fd, '?')}")
        real_fsync(fd)
        _done()

    os.open, os.fsync = open_, fsync_  # type: ignore[assignment]
    for name in ("replace", "rename", "link", "remove"):
        setattr(os, name, _wrap(name, getattr(os, name), root))
    real_move = _win.move_file_ex

    def move_(src: str, dst: str, flags: int) -> None:
        _event(f"movefileex {_short(src, root)} {_short(dst, root)} {flags}")
        real_move(src, dst, flags)
        _done()

    _win.move_file_ex = move_


def main() -> None:
    global _log_fd, _limits
    scenario, target, log, before, after = sys.argv[1:]
    _limits = (int(before), int(after))
    _log_fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    _install(os.path.dirname(os.path.abspath(target)))
    with atomic_write(target, "wb", **SCENARIOS[scenario]) as f:
        for start in range(0, len(NEW), 8192):
            f.write(NEW[start : start + 8192])
    _event("returned")


if __name__ == "__main__":
    main()
