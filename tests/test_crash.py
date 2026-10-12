"""Kill a writer process at random moments and check the target is never torn.

A process kill tests atomicity (readers and the next run see the old or the new
file, never a mix). It does not test power-loss durability, which no portable
test can simulate.
"""

from __future__ import annotations

import os
import random
import time
from pathlib import Path

import pytest
from _payload import make_payload, parse_payload
from conftest import spawn_worker

from durablewrite import cleanup_temp_files, write_bytes_atomic

SEED = int(os.environ.get("DURABLEWRITE_CRASH_SEED", "20261012"))
ITERATIONS = int(os.environ.get("DURABLEWRITE_CRASH_ITERATIONS", "40"))


@pytest.mark.slow
def test_killing_a_writer_never_leaves_a_partial_target(tmp_path: Path) -> None:
    rng = random.Random(SEED)
    target = tmp_path / "state.bin"
    write_bytes_atomic(target, make_payload(0, 1024))
    generations: set[int] = set()
    leaked_temp_files = 0
    for iteration in range(ITERATIONS):
        child = spawn_worker("loop", str(target), str(rng.randint(64, 1024) * 1024))
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "started"
        time.sleep(rng.uniform(0.0, 0.25))
        child.kill()
        child.wait(timeout=30)
        child.stdout.close()
        context = f"seed={SEED} iteration={iteration}"
        try:
            generation, _ = parse_payload(target.read_bytes())
        except AssertionError as exc:
            raise AssertionError(f"torn target ({context}): {exc}") from None
        generations.add(generation)
        leaked_temp_files += len(cleanup_temp_files(tmp_path, older_than=0))
        assert sorted(p.name for p in tmp_path.iterdir()) == ["state.bin"], context
    # The kills must have landed at different points, including mid-write.
    assert len(generations) > ITERATIONS // 4, sorted(generations)
    assert leaked_temp_files > 0, "no kill interrupted a write; the test proved nothing"
