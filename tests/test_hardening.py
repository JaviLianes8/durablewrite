"""Edge cases: private temp files, locked temp files, name collisions, odd paths."""

from __future__ import annotations

import math
import os
import stat
import subprocess
import time
from pathlib import Path

import pytest
from conftest import can_symlink, is_root, leftovers, posix_only, spawn_worker, windows_only

from durablewrite import (
    DirectorySyncError,
    RetryPolicy,
    SharingViolationError,
    atomic_write,
    cleanup_temp_files,
    write_json_atomic,
    write_text_atomic,
)


def _temp_files(directory: Path) -> list[Path]:
    return [p for p in directory.iterdir() if p.name.endswith(".dwtmp")]


def _temp_mode_during_write(target: Path, permissions: int | None = None) -> int:
    with atomic_write(target, permissions=permissions) as f:
        f.write("s3cret")
        f.flush()
        (temp,) = _temp_files(target.parent)
        return stat.S_IMODE(temp.stat().st_mode)


@posix_only
def test_temp_file_is_private_when_explicit_permissions_are_given(tmp_path: Path) -> None:
    old = os.umask(0o022)
    try:
        assert _temp_mode_during_write(tmp_path / "token", permissions=0o600) == 0o600
    finally:
        os.umask(old)
    assert stat.S_IMODE((tmp_path / "token").stat().st_mode) == 0o600


@posix_only
def test_temp_file_is_private_when_replacing_a_private_file(tmp_path: Path) -> None:
    target = tmp_path / "token"
    target.write_text("old")
    target.chmod(0o600)
    old = os.umask(0o022)
    try:
        assert _temp_mode_during_write(target) == 0o600
    finally:
        os.umask(old)


@posix_only
def test_directory_sync_failure_is_reported_after_the_replace(tmp_path: Path) -> None:
    if is_root():
        pytest.skip("root can read any directory")
    locked = tmp_path / "locked"
    locked.mkdir()
    target = locked / "f.txt"
    locked.chmod(0o300)  # write and search, but no read: the dir cannot be opened
    try:
        with pytest.raises(DirectorySyncError) as info:
            write_text_atomic(target, "new")
        assert target.read_text(encoding="utf-8") == "new"
        assert info.value.filename == str(locked)
    finally:
        locked.chmod(0o700)


def _kill(child: subprocess.Popen[str]) -> None:
    child.kill()
    child.wait(timeout=30)
    assert child.stdout is not None
    child.stdout.close()


@windows_only
def test_a_locked_temp_file_is_still_removed_once_released(tmp_path: Path) -> None:
    target = tmp_path / "t.txt"
    target.write_text("old", encoding="utf-8")
    holder: list[subprocess.Popen[str]] = []
    sleeps: list[float] = []

    def sleep(delay: float) -> None:
        sleeps.append(delay)
        if len(sleeps) == 5:  # the first wait of the removal phase
            _kill(holder.pop())
        elif len(sleeps) > 5:  # a virus scanner may open the file for a moment
            time.sleep(0.2)

    policy = RetryPolicy(max_attempts=5, initial_delay=0.0, sleep=sleep)
    try:
        with pytest.raises(SharingViolationError), atomic_write(target, retry=policy) as f:
            f.write("new")
            f.flush()
            (temp,) = _temp_files(tmp_path)
            child = spawn_worker("hold", str(temp), "60")
            assert child.stdout is not None
            assert child.stdout.readline().strip() == "holding"
            holder.append(child)
    finally:
        while holder:  # never leave the holder running when the test fails
            _kill(holder.pop())
    assert len(sleeps) >= 5, "the holder was never released"
    assert target.read_text(encoding="utf-8") == "old"
    assert leftovers(tmp_path, target.name) == []


def test_cleanup_for_one_target_ignores_targets_sharing_a_prefix(tmp_path: Path) -> None:
    other = tmp_path / ".foo.txt.deadbeef.dwtmp"
    other.write_bytes(b"x")
    assert cleanup_temp_files(tmp_path, older_than=0, target=tmp_path / "foo") == []
    assert other.exists()


def test_long_names_sharing_a_head_get_distinct_temp_files(tmp_path: Path) -> None:
    first, second = tmp_path / ("x" * 60 + "a"), tmp_path / ("x" * 60 + "b")
    with atomic_write(first) as f1, atomic_write(second) as f2:
        f1.write("1")
        f2.write("2")
        stems = {p.name.rsplit(".", 2)[0] for p in _temp_files(tmp_path)}
        assert len(stems) == 2, stems
    assert first.read_text(encoding="utf-8") == "1"
    assert second.read_text(encoding="utf-8") == "2"
    assert _temp_files(tmp_path) == []


def test_cleanup_for_one_long_target_removes_only_its_files(tmp_path: Path) -> None:
    first = tmp_path / ("y" * 70 + "1")
    with pytest.raises(RuntimeError), atomic_write(first) as f:
        (temp,) = _temp_files(tmp_path)
        copy = tmp_path / temp.name
        f.write("x")
        raise RuntimeError
    copy.write_bytes(b"left by a killed writer")
    stray = tmp_path / f".{'y' * 39}~00000000.0123abcd.dwtmp"
    stray.write_bytes(b"x")
    assert cleanup_temp_files(tmp_path, older_than=0, target=first) == [str(copy)]
    assert stray.exists()


@pytest.mark.parametrize("suffix", ["/", os.sep])
def test_a_path_ending_with_a_separator_is_rejected(tmp_path: Path, suffix: str) -> None:
    with pytest.raises(ValueError, match="separator"):
        write_text_atomic(str(tmp_path / "newdir") + suffix, "x")
    assert list(tmp_path.iterdir()) == []


@posix_only
def test_no_follow_replaces_a_symlink_to_a_directory(tmp_path: Path) -> None:
    if not can_symlink(tmp_path):
        pytest.skip("symlinks are not available to this user")
    (tmp_path / "dir").mkdir()
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "dir")
    write_text_atomic(link, "file now", follow_symlinks=False)
    assert not link.is_symlink()
    assert link.read_text(encoding="utf-8") == "file now"
    assert stat.S_IMODE(link.stat().st_mode) != stat.S_IMODE((tmp_path / "dir").stat().st_mode)


def test_json_refuses_nan_unless_allowed(tmp_path: Path) -> None:
    target = tmp_path / "c.json"
    with pytest.raises(ValueError):
        write_json_atomic(target, {"x": math.nan})
    assert list(tmp_path.iterdir()) == []
    write_json_atomic(target, {"x": math.inf}, allow_nan=True, indent=None)
    assert target.read_text(encoding="utf-8") == '{"x": Infinity}\n'
