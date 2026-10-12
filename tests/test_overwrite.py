from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from conftest import child_env, leftovers

from durablewrite import atomic_write, write_bytes_atomic, write_text_atomic


def test_no_overwrite_creates_a_missing_file(tmp_path: Path) -> None:
    target = tmp_path / "once.txt"
    write_text_atomic(target, "first", overwrite=False)
    assert target.read_text(encoding="utf-8") == "first"
    assert leftovers(tmp_path, target.name) == []


def test_no_overwrite_refuses_an_existing_file_up_front(tmp_path: Path) -> None:
    target = tmp_path / "once.txt"
    target.write_text("first", encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_text_atomic(target, "second", overwrite=False)
    assert target.read_text(encoding="utf-8") == "first"
    assert leftovers(tmp_path, target.name) == []


def test_no_overwrite_detects_a_file_created_during_the_write(tmp_path: Path) -> None:
    target = tmp_path / "once.txt"
    with pytest.raises(FileExistsError), atomic_write(target, "wb", overwrite=False) as f:
        f.write(b"loser")
        target.write_bytes(b"winner")
    assert target.read_bytes() == b"winner"
    assert leftovers(tmp_path, target.name) == []


_RACER = """
import sys
from durablewrite import write_bytes_atomic
try:
    write_bytes_atomic(sys.argv[1], sys.argv[2].encode(), overwrite=False, fsync="none")
except FileExistsError:
    print("lost")
else:
    print("won")
"""


@pytest.mark.slow
def test_exactly_one_of_many_racing_processes_creates_the_file(tmp_path: Path) -> None:
    target = tmp_path / "winner.txt"
    racers = [
        subprocess.Popen(
            [sys.executable, "-c", _RACER, str(target), f"racer-{n}"],
            stdout=subprocess.PIPE,
            text=True,
            env=child_env(),
        )
        for n in range(6)
    ]
    outcomes = [racer.communicate(timeout=60)[0].strip() for racer in racers]
    assert sorted(outcomes) == ["lost"] * 5 + ["won"]
    winner = outcomes.index("won")
    assert target.read_bytes() == f"racer-{winner}".encode()
    assert leftovers(tmp_path, target.name) == []


def test_bytes_helper_supports_no_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "b.bin"
    write_bytes_atomic(target, b"1", overwrite=False)
    with pytest.raises(FileExistsError):
        write_bytes_atomic(target, b"2", overwrite=False)
    assert target.read_bytes() == b"1"
