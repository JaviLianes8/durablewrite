"""Fsync levels and the retry policy used when the final rename is blocked."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Literal

from ._check import check_flag, check_real

FsyncLevel = Literal["none", "file", "full"]
"""How much to flush to stable storage before a write returns.

``"none"``: no flush. The write is still atomic for readers and survives a
crash of the writing process, but not a power loss or an OS crash.
``"file"``: flush the temp file before the rename, so the new content is on
disk before its name can point at it.
``"full"`` (the default): ``"file"``, then make the rename itself durable. On
POSIX the parent directory is fsynced after the rename; on Windows, which has
no directory fsync, the rename is made with ``MOVEFILE_WRITE_THROUGH``. On
macOS every flush uses ``F_FULLFSYNC``.

>>> import os, tempfile
>>> from durablewrite import write_text_atomic
>>> with tempfile.TemporaryDirectory() as folder:
...     for level in ("none", "file", "full"):
...         write_text_atomic(os.path.join(folder, level), level, fsync=level)
...     print(sorted(os.listdir(folder)))
['file', 'full', 'none']
"""

_LEVELS: dict[str, tuple[bool, bool]] = {
    "none": (False, False),
    "file": (True, False),
    "full": (True, True),
}


def resolve_fsync(fsync: FsyncLevel | None, durable: bool, fsync_dir: bool) -> tuple[bool, bool]:
    """Return ``(sync_file, sync_dir)``; an explicit ``fsync`` wins over the flags."""
    flags = check_flag("durable", durable), check_flag("fsync_dir", fsync_dir)
    if fsync is None:
        return flags
    if not isinstance(fsync, str):
        raise TypeError("fsync must be a str")
    if fsync not in _LEVELS:
        raise ValueError("fsync must be 'none', 'file' or 'full'")
    return _LEVELS[fsync]


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded exponential backoff for a rename that a Windows lock blocks.

    Only transient Windows lock errors are retried (see
    :class:`~durablewrite.SharingViolationError`). Every other error, including
    a read-only target and any POSIX ``EACCES``, is raised on the first attempt.
    With the defaults the writer waits at most about 1.1 seconds in total.

    ``max_attempts`` counts every rename attempt, so ``1`` disables retrying.
    The wait before attempt ``n + 1`` is ``initial_delay * multiplier**(n - 1)``,
    capped at ``max_delay``. ``sleep`` is injectable for tests. Delays must be
    finite and not negative, ``multiplier`` at least 1; a wrong type raises
    :class:`TypeError` and a bad value :class:`ValueError`.

    >>> list(RetryPolicy(max_attempts=4, initial_delay=0.1, max_delay=0.3).delays())
    [0.1, 0.2, 0.3]
    """

    max_attempts: int = 8
    initial_delay: float = 0.01
    multiplier: float = 2.0
    max_delay: float = 0.5
    sleep: Callable[[float], None] = field(default=time.sleep, compare=False, repr=False)

    def __post_init__(self) -> None:
        attempts = self.max_attempts
        if isinstance(attempts, bool) or not isinstance(attempts, int):
            raise TypeError("max_attempts must be an int")
        if attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        check_real("initial_delay", self.initial_delay)
        check_real("max_delay", self.max_delay)
        check_real("multiplier", self.multiplier, minimum=1.0)
        if not callable(self.sleep):
            raise TypeError("sleep must be callable")

    def delays(self) -> Iterator[float]:
        """Yield the wait before each retry: ``max_attempts - 1`` values."""
        delay, cap, factor = (
            float(self.initial_delay),
            float(self.max_delay),
            float(self.multiplier),
        )
        for _ in range(self.max_attempts - 1):
            yield min(delay, cap)
            delay = min(delay * factor, cap)


DEFAULT_RETRY = RetryPolicy()
"""The policy used when none is given: 8 attempts, about 1.1 seconds at most.

>>> DEFAULT_RETRY.max_attempts, round(sum(DEFAULT_RETRY.delays()), 2)
(8, 1.13)
"""

NO_RETRY = RetryPolicy(max_attempts=1)
"""Fail on the first blocked rename.

>>> NO_RETRY.max_attempts, list(NO_RETRY.delays())
(1, [])
"""
