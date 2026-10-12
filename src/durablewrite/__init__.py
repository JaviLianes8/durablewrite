"""Durable, cross-platform atomic file writes (temp-same-dir, os.replace, fsync)."""

from __future__ import annotations

from ._atomic import atomic_write
from ._cleanup import cleanup_temp_files
from ._errors import DurableWriteError, SharingViolationError
from ._helpers import write_bytes_atomic, write_json_atomic, write_text_atomic
from ._options import DEFAULT_RETRY, NO_RETRY, FsyncLevel, RetryPolicy

__version__ = "0.2.0"

__all__ = [
    "DEFAULT_RETRY",
    "NO_RETRY",
    "DurableWriteError",
    "FsyncLevel",
    "RetryPolicy",
    "SharingViolationError",
    "atomic_write",
    "cleanup_temp_files",
    "write_bytes_atomic",
    "write_json_atomic",
    "write_text_atomic",
]
