"""A reader in another process holds the target open while we replace it."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from conftest import leftovers, posix_only, spawn_worker, windows_only

from durablewrite import (
    NO_RETRY,
    RetryPolicy,
    SharingViolationError,
    write_text_atomic,
)


def _hold(target: Path, seconds: float) -> subprocess.Popen[str]:
    child = spawn_worker("hold", str(target), str(seconds))
    assert child.stdout is not None
    assert child.stdout.readline().strip() == "holding"
    return child


def _finish(child: subprocess.Popen[str]) -> None:
    child.wait(timeout=30)
    assert child.stdout is not None
    child.stdout.close()


@windows_only
def test_retry_waits_for_a_reader_to_let_go(tmp_path: Path) -> None:
    target = tmp_path / "held.txt"
    target.write_text("old", encoding="utf-8")
    child = _hold(target, 0.4)
    policy = RetryPolicy(max_attempts=60, initial_delay=0.01, max_delay=0.05)
    write_text_atomic(target, "new", retry=policy)
    _finish(child)
    assert target.read_text(encoding="utf-8") == "new"
    assert leftovers(tmp_path, target.name) == []


@windows_only
def test_exhausted_retry_raises_and_leaves_target_and_no_temp(tmp_path: Path) -> None:
    target = tmp_path / "held.txt"
    target.write_text("old", encoding="utf-8")
    delays: list[float] = []
    policy = RetryPolicy(max_attempts=4, initial_delay=0.01, sleep=delays.append)
    child = _hold(target, 5)
    try:
        with pytest.raises(SharingViolationError) as info:
            write_text_atomic(target, "new", retry=policy)
    finally:
        child.kill()
        _finish(child)
    assert info.value.attempts == 4
    assert delays == [0.01, 0.02, 0.04]
    assert getattr(info.value.__cause__, "winerror", None) in (5, 32, 33)
    assert target.read_text(encoding="utf-8") == "old"
    assert leftovers(tmp_path, target.name) == []


@windows_only
def test_no_retry_fails_on_the_first_blocked_rename(tmp_path: Path) -> None:
    target = tmp_path / "held.txt"
    target.write_text("old", encoding="utf-8")
    child = _hold(target, 5)
    try:
        with pytest.raises(SharingViolationError) as info:
            write_text_atomic(target, "new", retry=NO_RETRY)
    finally:
        child.kill()
        _finish(child)
    assert info.value.attempts == 1


@windows_only
def test_read_only_target_is_not_retried(tmp_path: Path) -> None:
    target = tmp_path / "ro.txt"
    target.write_text("old", encoding="utf-8")
    os.chmod(target, 0o444)
    delays: list[float] = []
    try:
        with pytest.raises(PermissionError) as info:
            write_text_atomic(target, "new", retry=RetryPolicy(sleep=delays.append))
    finally:
        os.chmod(target, 0o666)
    assert not isinstance(info.value, SharingViolationError)
    assert delays == []
    assert target.read_text(encoding="utf-8") == "old"
    assert leftovers(tmp_path, target.name) == []


@posix_only
def test_posix_replace_succeeds_while_a_reader_keeps_the_old_inode(tmp_path: Path) -> None:
    target = tmp_path / "held.txt"
    target.write_text("old", encoding="utf-8")
    with open(target, encoding="utf-8") as reader:
        write_text_atomic(target, "new", retry=NO_RETRY)
        assert reader.read() == "old"
    assert target.read_text(encoding="utf-8") == "new"
