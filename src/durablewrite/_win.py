"""Windows rename through ``MoveFileExW`` with ``MOVEFILE_WRITE_THROUGH``."""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable

MOVEFILE_REPLACE_EXISTING = 0x1
MOVEFILE_WRITE_THROUGH = 0x8

MoveFileEx = Callable[[str, str, int], int]


def _kernel32_move() -> MoveFileEx:
    if sys.platform != "win32":
        raise OSError("MoveFileExW is only available on Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    function = kernel32.MoveFileExW
    function.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32)
    function.restype = ctypes.c_int
    move: MoveFileEx = function
    return move


_move: MoveFileEx | None = None


def move_file_ex(src: str, dst: str, flags: int) -> None:
    """Call ``MoveFileExW(src, dst, flags)`` and raise :class:`OSError` on failure.

    The error carries ``winerror`` and both names, exactly like the one
    :func:`os.replace` raises, so callers handle both the same way.
    """
    global _move
    if _move is None:
        _move = _kernel32_move()
    if _move(src, dst, flags):
        return
    code, message = 0, "rename failed"
    if sys.platform == "win32":
        code = ctypes.get_last_error()
        message = ctypes.FormatError(code)
    raise OSError(0, message, src, code, dst)


def windows_move(*, replace: bool) -> Callable[[str, str], None]:
    """Return a rename that also asks Windows to write the move through to disk."""
    flags = MOVEFILE_WRITE_THROUGH | (MOVEFILE_REPLACE_EXISTING if replace else 0)

    def move(src: str, dst: str) -> None:
        move_file_ex(src, dst, flags)

    return move
