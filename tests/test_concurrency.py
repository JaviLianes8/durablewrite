"""Several processes replace one file at once while this process keeps reading it."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from _payload import make_payload, parse_payload
from conftest import leftovers, spawn_worker

from durablewrite import write_bytes_atomic

WRITERS = 4
WRITES_EACH = 200


@pytest.mark.slow
def test_concurrent_writers_never_expose_a_torn_file(tmp_path: Path) -> None:
    target = tmp_path / "shared.bin"
    write_bytes_atomic(target, make_payload(0, 1024, writer=99))
    children = [
        spawn_worker("writes", str(target), str(writer), str(WRITES_EACH))
        for writer in range(WRITERS)
    ]
    seen: set[tuple[int, int]] = set()
    blocked_reads = 0
    while any(child.poll() is None for child in children):
        try:
            data = target.read_bytes()
        except (PermissionError, FileNotFoundError):
            # Windows may refuse an open, or briefly miss the name, while a rename
            # onto it is in flight (see the guide); never on POSIX.
            assert os.name == "nt"
            blocked_reads += 1
            continue
        seen.add(parse_payload(data))
        time.sleep(0.001)
    for child in children:
        assert child.stdout is not None
        assert child.stdout.read().strip() == "done", "a writer failed"
        child.stdout.close()
        assert child.returncode == 0
    generation, writer = parse_payload(target.read_bytes())
    assert generation == WRITES_EACH, "the last write of some writer must win"
    assert writer in range(WRITERS)
    assert len(seen) > 1, "the reader never observed a change"
    assert leftovers(tmp_path, target.name) == []
