"""Permissions, ownership, symlinks and path edge cases on the real filesystem."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from conftest import can_symlink, leftovers, posix_only

from durablewrite import atomic_write, write_text_atomic


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@posix_only
def test_new_file_honours_the_umask_like_open(tmp_path: Path) -> None:
    old = os.umask(0o027)
    try:
        write_text_atomic(tmp_path / "new.txt", "x")
        (tmp_path / "plain.txt").write_text("x")
    finally:
        os.umask(old)
    assert _mode(tmp_path / "new.txt") == _mode(tmp_path / "plain.txt") == 0o640


@posix_only
def test_existing_mode_is_preserved(tmp_path: Path) -> None:
    target = tmp_path / "run.sh"
    target.write_text("old")
    target.chmod(0o751)
    write_text_atomic(target, "new")
    assert _mode(target) == 0o751


@posix_only
def test_preserve_mode_can_be_turned_off(tmp_path: Path) -> None:
    target = tmp_path / "run.sh"
    target.write_text("old")
    target.chmod(0o700)
    old = os.umask(0o022)
    try:
        write_text_atomic(target, "new", preserve_mode=False)
    finally:
        os.umask(old)
    assert _mode(target) == 0o644


@posix_only
def test_explicit_permissions_win(tmp_path: Path) -> None:
    target = tmp_path / "secret"
    target.write_text("old")
    target.chmod(0o644)
    write_text_atomic(target, "new", permissions=0o600)
    assert _mode(target) == 0o600


@posix_only
def test_preserve_owner_keeps_uid_and_gid(tmp_path: Path) -> None:
    target = tmp_path / "owned"
    target.write_text("old")
    before = target.stat()
    write_text_atomic(target, "new", preserve_owner=True)
    after = target.stat()
    assert (after.st_uid, after.st_gid) == (before.st_uid, before.st_gid)


def test_permissions_read_only_is_applied(tmp_path: Path) -> None:
    target = tmp_path / "frozen.txt"
    write_text_atomic(target, "x", permissions=0o444)
    try:
        # Mode bits, not os.access: root may write to a 0o444 file on POSIX.
        assert not _mode(target) & stat.S_IWUSR
    finally:
        target.chmod(0o644)


def test_writing_through_a_symlink_updates_the_target_and_keeps_the_link(tmp_path: Path) -> None:
    if not can_symlink(tmp_path):
        pytest.skip("symlinks are not available to this user")
    real = tmp_path / "real.txt"
    real.write_text("old", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(real)
    write_text_atomic(link, "new")
    assert link.is_symlink()
    assert real.read_text(encoding="utf-8") == "new"
    assert leftovers(tmp_path, "real.txt") == ["link.txt"]


def test_no_follow_replaces_the_link_itself(tmp_path: Path) -> None:
    if not can_symlink(tmp_path):
        pytest.skip("symlinks are not available to this user")
    real = tmp_path / "real.txt"
    real.write_text("old", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(real)
    write_text_atomic(link, "new", follow_symlinks=False)
    assert not link.is_symlink()
    assert link.read_text(encoding="utf-8") == "new"
    assert real.read_text(encoding="utf-8") == "old"


def test_symlink_into_another_directory_keeps_the_temp_beside_the_target(tmp_path: Path) -> None:
    if not can_symlink(tmp_path):
        pytest.skip("symlinks are not available to this user")
    (tmp_path / "data").mkdir()
    (tmp_path / "links").mkdir()
    real = tmp_path / "data" / "real.txt"
    real.write_text("old", encoding="utf-8")
    link = tmp_path / "links" / "link.txt"
    link.symlink_to(real)
    with atomic_write(link) as f:
        f.write("new")
        assert len(list((tmp_path / "data").iterdir())) == 2
        assert [p.name for p in (tmp_path / "links").iterdir()] == ["link.txt"]
    assert real.read_text(encoding="utf-8") == "new"


def test_a_directory_target_is_rejected_without_a_temp_file(tmp_path: Path) -> None:
    with pytest.raises(IsADirectoryError):
        write_text_atomic(tmp_path, "x")
    assert list(tmp_path.iterdir()) == []


def test_an_empty_path_is_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        write_text_atomic("", "x")


def test_a_missing_directory_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        write_text_atomic(tmp_path / "nope" / "f.txt", "x")


def test_a_long_file_name_does_not_overflow_the_temp_name(tmp_path: Path) -> None:
    target = tmp_path / ("n" * 240)
    write_text_atomic(target, "x")
    assert target.read_text(encoding="utf-8") == "x"
    assert leftovers(tmp_path, target.name) == []


def test_temp_name_carries_the_cleanup_suffix(tmp_path: Path) -> None:
    target = tmp_path / "state.txt"
    with atomic_write(target) as f:
        f.write("x")
        names = leftovers(tmp_path, target.name)
    assert len(names) == 1
    assert names[0].startswith(".state.txt.")
    assert names[0].endswith(".dwtmp")


def test_a_dangling_symlink_creates_its_target(tmp_path: Path) -> None:
    if not can_symlink(tmp_path):
        pytest.skip("symlinks are not available to this user")
    link = tmp_path / "link.txt"
    link.symlink_to(tmp_path / "real.txt")
    write_text_atomic(link, "new")
    assert link.is_symlink()
    assert (tmp_path / "real.txt").read_text(encoding="utf-8") == "new"
