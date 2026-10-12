"""Exceptions raised by durablewrite itself."""

from __future__ import annotations


class DurableWriteError(OSError):
    """Base class for errors that durablewrite raises on its own.

    It subclasses :class:`OSError`, so code that already handles ``OSError``
    around a file write keeps working unchanged.
    """


class SharingViolationError(DurableWriteError, PermissionError):
    """The target stayed locked by another process for the whole retry budget.

    Raised on Windows when ``MoveFileExW`` keeps failing with
    ``ERROR_ACCESS_DENIED``, ``ERROR_SHARING_VIOLATION`` or
    ``ERROR_LOCK_VIOLATION`` because something holds the target (or the fresh
    temp file) open without ``FILE_SHARE_DELETE``: another process, an antivirus
    scanner or the search indexer. The original target is untouched and the temp
    file has been removed. ``attempts`` is the number of rename attempts made. The last
    underlying error, with its ``winerror`` code, is chained as ``__cause__``.
    """

    attempts: int = 0
