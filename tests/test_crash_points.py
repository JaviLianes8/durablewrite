"""Kill a writer right before and right after every file system call it makes.

The child (``_crashpoint.py``) logs each call and kills itself with no cleanup
at call number k, for every k. Whatever the point, the target must hold the old
content until the rename has completed and the new content from then on, and
a leftover temp file must be one that ``cleanup_temp_files`` reclaims.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import TESTS_DIR, child_env

from durablewrite import cleanup_temp_files

OLD = b"old content"
NEW = b"new content " * 4000
CHILD = TESTS_DIR / "_crashpoint.py"
PUBLISH = ("replace", "movefileex", "link")

if os.name == "nt":
    EXPECTED = {
        "replace": ["open temp", "fsync temp", "movefileex temp t 9"],
        "replace-file": ["open temp", "fsync temp", "replace temp t"],
        "replace-none": ["open temp", "replace temp t"],
        "create": ["open temp", "fsync temp", "movefileex temp t 9"],
        "exclusive": ["open temp", "fsync temp", "movefileex temp t 8"],
    }
else:
    EXPECTED = {
        "replace": ["open temp", "fsync temp", "replace temp t", "open .", "fsync ."],
        "replace-file": ["open temp", "fsync temp", "replace temp t"],
        "replace-none": ["open temp", "replace temp t"],
        "create": ["open temp", "fsync temp", "replace temp t", "open .", "fsync ."],
        "exclusive": [
            "open temp",
            "fsync temp",
            "link temp t",
            "remove temp",
            "open .",
            "fsync .",
        ],
    }


def _run(folder: Path, scenario: str, before: int = 0, after: int = 0) -> tuple[int, list[str]]:
    log = folder.parent / f"{folder.name}.log"
    log.unlink(missing_ok=True)
    child = subprocess.run(
        [
            sys.executable,
            str(CHILD),
            scenario,
            str(folder / "t"),
            str(log),
            str(before),
            str(after),
        ],
        env=child_env(),
        timeout=120,
        capture_output=True,
    )
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return child.returncode, lines


def _prepare(folder: Path, scenario: str) -> None:
    folder.mkdir()
    if scenario.startswith("replace"):
        (folder / "t").write_bytes(OLD)


@pytest.mark.parametrize("scenario", sorted(EXPECTED))
def test_the_call_sequence_is_flush_then_rename_then_directory(
    tmp_path: Path, scenario: str
) -> None:
    folder = tmp_path / "run"
    _prepare(folder, scenario)
    code, events = _run(folder, scenario)
    assert code == 0
    assert events == [*EXPECTED[scenario], "returned"]
    assert (folder / "t").read_bytes() == NEW
    assert os.listdir(folder) == ["t"]


@pytest.mark.slow
@pytest.mark.parametrize("scenario", sorted(EXPECTED))
def test_a_kill_at_any_call_leaves_the_old_or_the_complete_new_file(
    tmp_path: Path, scenario: str
) -> None:
    calls = EXPECTED[scenario]
    published = next(i for i, call in enumerate(calls, 1) if call.startswith(PUBLISH))
    for k in range(1, len(calls) + 1):
        for when in ("before", "after"):
            folder = tmp_path / f"{when}{k}"
            _prepare(folder, scenario)
            code, events = _run(folder, scenario, *((k, 0) if when == "before" else (0, k)))
            context = f"{scenario}: killed {when} call {k} ({calls[k - 1]})"
            assert code != 0, context
            assert events == calls[: k if when == "after" else k - 1], context
            done = k > published or (k == published and when == "after")
            target = folder / "t"
            if done:
                assert target.read_bytes() == NEW, context
            elif scenario.startswith("replace"):
                assert target.read_bytes() == OLD, context
            else:
                assert not target.exists(), context
            temps = [p for p in os.listdir(folder) if p != "t"]
            assert all(p.endswith(".dwtmp") for p in temps), context
            assert len(cleanup_temp_files(folder, older_than=0)) == len(temps), context
            assert os.listdir(folder) == (["t"] if target.exists() else []), context
