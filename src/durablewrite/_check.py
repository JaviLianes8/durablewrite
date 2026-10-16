"""Argument checks that run before any file is touched, with short messages."""

from __future__ import annotations

import codecs
import math
import os
from typing import Any

_NEWLINES = (None, "", "\n", "\r", "\r\n")


def check_path(path: Any) -> str:
    """Return ``path`` as a ``str``; bytes and other types are a :class:`TypeError`."""
    try:
        text = os.fspath(path)
    except TypeError:
        raise TypeError("path must be a str or an os.PathLike[str]") from None
    if not isinstance(text, str):
        raise TypeError("path must be a str or an os.PathLike[str], not bytes")
    if "\x00" in text:
        raise ValueError("path must not contain a NUL character")
    return text


def check_target(path: Any) -> str:
    """Like :func:`check_path`, and the path must name a file."""
    text = check_path(path)
    if not text:
        raise ValueError("path must not be empty")
    if text.endswith(os.sep) or (os.altsep is not None and text.endswith(os.altsep)):
        raise ValueError("path must name a file, not end with a separator")
    return text


def check_permissions(permissions: object) -> int | None:
    """Permission bits must be an int from 0 to 0o7777 (or None)."""
    if permissions is None:
        return None
    if isinstance(permissions, bool) or not isinstance(permissions, int):
        raise TypeError("permissions must be an int such as 0o644")
    if not 0 <= permissions <= 0o7777:
        raise ValueError("permissions must be between 0 and 0o7777")
    return permissions


def check_text_options(binary: bool, encoding: object, newline: object) -> None:
    """Validate ``encoding`` and ``newline`` the way :func:`open` would, but up front."""
    if binary:
        if encoding is not None:
            raise ValueError("encoding is not allowed in binary mode")
        if newline is not None:
            raise ValueError("newline is not allowed in binary mode")
        return
    if encoding is not None:
        if not isinstance(encoding, str):
            raise TypeError("encoding must be a str")
        try:
            codecs.lookup(encoding)
        except LookupError:
            raise LookupError("unknown encoding") from None
    if newline is not None and not isinstance(newline, str):
        raise TypeError("newline must be a str or None")
    if newline not in _NEWLINES:
        raise ValueError("newline must be None, '', '\\n', '\\r' or '\\r\\n'")


def check_real(name: str, value: object, *, minimum: float | None = 0.0) -> float:
    """Return ``value`` as a finite float, at least ``minimum`` unless that is None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    try:
        number = float(value)
    except OverflowError:
        raise ValueError(f"{name} must be finite") from None
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and number < minimum:
        floor = "not be negative" if minimum == 0 else f"be at least {minimum:g}"
        raise ValueError(f"{name} must {floor}")
    return number
