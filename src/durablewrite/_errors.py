"""Exceptions raised by durablewrite itself."""

from __future__ import annotations


class DurableWriteError(OSError):
    """Base class for errors that durablewrite raises on its own.

    It subclasses :class:`OSError`, so code that already handles ``OSError``
    around a file write keeps working unchanged.

    >>> issubclass(DurableWriteError, OSError)
    True
    """


class SharingViolationError(DurableWriteError, PermissionError):
    """The target stayed locked by another process for the whole retry budget.

    Raised on Windows when ``MoveFileExW`` keeps failing with
    ``ERROR_ACCESS_DENIED``, ``ERROR_SHARING_VIOLATION`` or
    ``ERROR_LOCK_VIOLATION`` because something holds the target (or the fresh
    temp file) open without ``FILE_SHARE_DELETE``: another process, an antivirus
    scanner or the search indexer. A directory ACL that denies the rename looks
    the same to Windows and ends here too. The original target is untouched.
    The temp file is removed, retrying under the same policy while it is locked;
    if it stays locked it is left for :func:`~durablewrite.cleanup_temp_files`.
    ``attempts`` is the number of rename attempts made. The last underlying
    error, with its ``winerror`` code, is chained as ``__cause__``.

    >>> error = SharingViolationError(13, "rename kept failing", "data.json")
    >>> isinstance(error, PermissionError), error.filename, error.attempts
    (True, 'data.json', 0)
    """

    attempts: int = 0


class DirectorySyncError(DurableWriteError):
    """The file was replaced, but its directory could not be fsynced afterwards.

    The new content is in place and readers see it, but the rename may not
    survive a power loss. Raised only with ``fsync="full"`` on POSIX, for
    example when the directory cannot be opened for reading or the filesystem
    refuses to fsync directories. ``filename`` is the directory; the
    underlying error is chained as ``__cause__``.

    >>> error = DirectorySyncError(5, "file replaced, but its directory was not synced", "data")
    >>> isinstance(error, DurableWriteError), error.filename
    (True, 'data')
    """
