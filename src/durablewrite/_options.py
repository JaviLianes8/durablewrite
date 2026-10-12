"""Fsync levels and the retry policy used when the final rename is blocked."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Literal

FsyncLevel = Literal["none", "file", "full"]
"""How much to flush to stable storage.

``"none"``: no fsync at all. The write is still atomic for readers and survives
a crash of the writing process, but not a power loss or kernel crash.
``"file"``: fsync the temp file before the rename, so the new content is on disk
before its name can point at it.
``"full"``: ``"file"`` plus an fsync of the parent directory after the rename, so
the rename itself is durable. Windows has no directory fsync, so there
``"full"`` behaves like ``"file"``.
"""

_LEVELS: dict[str, tuple[bool, bool]] = {
    "none": (False, False),
    "file": (True, False),
    "full": (True, True),
}


def resolve_fsync(fsync: FsyncLevel | None, durable: bool, fsync_dir: bool) -> tuple[bool, bool]:
    """Return ``(sync_file, sync_dir)``; an explicit ``fsync`` wins over the flags."""
    if fsync is None:
        return durable, fsync_dir
    try:
        return _LEVELS[fsync]
    except KeyError:
        raise ValueError(f"fsync must be one of {sorted(_LEVELS)!r}, got {fsync!r}") from None


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded exponential backoff for a rename that a Windows lock blocks.

    Only transient Windows lock errors are retried (see
    :class:`~durablewrite.SharingViolationError`). Every other error, including
    a read-only target and any POSIX ``EACCES``, is raised on the first attempt.
    With the defaults the writer waits at most about 1.1 seconds in total.

    ``max_attempts`` counts every rename attempt, so ``1`` disables retrying.
    The wait before attempt ``n + 1`` is ``initial_delay * multiplier**(n - 1)``,
    capped at ``max_delay``. ``sleep`` is injectable for tests.
    """

    max_attempts: int = 8
    initial_delay: float = 0.01
    multiplier: float = 2.0
    max_delay: float = 0.5
    sleep: Callable[[float], None] = field(default=time.sleep, compare=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay < 0 or self.max_delay < 0:
            raise ValueError("delays must not be negative")
        if self.multiplier < 1:
            raise ValueError("multiplier must be at least 1")

    def delays(self) -> Iterator[float]:
        """Yield the wait before each retry: ``max_attempts - 1`` values."""
        delay = self.initial_delay
        for _ in range(self.max_attempts - 1):
            yield min(delay, self.max_delay)
            delay *= self.multiplier


DEFAULT_RETRY = RetryPolicy()
"""The policy used when none is given: 8 attempts, about 1.1 seconds at most."""

NO_RETRY = RetryPolicy(max_attempts=1)
"""Fail on the first blocked rename."""
