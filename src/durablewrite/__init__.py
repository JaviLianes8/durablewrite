"""Durable, cross-platform atomic file writes (temp-same-dir, os.replace, fsync)."""

from __future__ import annotations

from ._atomic import atomic_write, write_bytes_atomic, write_text_atomic

__version__ = "0.1.0"

__all__ = ["atomic_write", "write_bytes_atomic", "write_text_atomic"]
