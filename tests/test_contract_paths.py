"""A relative target is pinned when the write starts, whatever happens to the cwd."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from conftest import posix_only

from durablewrite import _write, atomic_write, cleanup_temp_files


def test_a_chdir_during_the_block_does_not_move_the_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    (first / "t").write_text("old a")
    (second / "t").write_text("old b")
    synced: list[str] = []
    monkeypatch.setattr(_write, "fsync_directory", synced.append)
    monkeypatch.chdir(first)
    with atomic_write("t") as f:
        f.write("new")
        os.chdir(second)
    assert (first / "t").read_text() == "new"
    assert (second / "t").read_text() == "old b"
    assert sorted(os.listdir(first)) == ["t"] and sorted(os.listdir(second)) == ["t"]
    assert [os.path.normcase(p) for p in synced] == [os.path.normcase(str(first))]


def test_a_relative_target_is_not_normalised_through_dot_dot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "d").mkdir()
    monkeypatch.chdir(tmp_path / "d")
    with atomic_write(os.path.join("..", "t")) as f:
        f.write("x")
    assert (tmp_path / "t").read_text() == "x"
    assert os.listdir(tmp_path / "d") == []


def _symlinked_tree(tmp_path: Path) -> Path:
    """tmp/far/deep and a link tmp/s -> far/deep; returns tmp."""
    (tmp_path / "far" / "deep").mkdir(parents=True)
    try:
        (tmp_path / "s").symlink_to(tmp_path / "far" / "deep", target_is_directory=True)
    except OSError:
        pytest.skip("symlinks are not available to this user")
    return tmp_path


@posix_only  # Win32 collapses ".." before it follows links, so there the plain path is right
def test_dot_dot_after_a_symlink_follows_the_link_like_the_kernel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _symlinked_tree(tmp_path)
    monkeypatch.chdir(root)
    synced: list[str] = []
    monkeypatch.setattr(_write, "fsync_directory", synced.append)
    with atomic_write(os.path.join("s", "..", "t")) as f:
        f.write("x")
        temps = [n for n in os.listdir(root / "far") if n.endswith(".dwtmp")]
        assert len(temps) == 1, "the temp file sits beside the real target"
    assert (root / "far" / "t").read_text() == "x"
    assert not (root / "t").exists()
    assert [os.path.realpath(p) for p in synced] == [os.path.realpath(root / "far")]


def test_a_relative_link_is_replaced_not_followed_without_follow_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "real").write_text("keep")
    try:
        (tmp_path / "lnk").symlink_to(tmp_path / "real")
    except OSError:
        pytest.skip("symlinks are not available to this user")
    monkeypatch.chdir(tmp_path)
    with atomic_write("lnk", follow_symlinks=False) as f:
        f.write("new")
    assert not (tmp_path / "lnk").is_symlink()
    assert (tmp_path / "lnk").read_text() == "new"
    assert (tmp_path / "real").read_text() == "keep"


def test_errors_before_the_block_name_the_path_as_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "e.txt").write_text("x")
    (tmp_path / "d").mkdir()
    with pytest.raises(FileExistsError) as taken:
        atomic_write("e.txt", overwrite=False).__enter__()
    with pytest.raises(IsADirectoryError) as folder:
        atomic_write("d").__enter__()
    assert (taken.value.filename, folder.value.filename) == ("e.txt", "d")


def test_cleanup_with_age_zero_removes_files_dated_in_the_future(tmp_path: Path) -> None:
    ahead = tmp_path / ".t.0123abcd.dwtmp"
    ahead.write_bytes(b"")
    future = 4_000_000_000
    os.utime(ahead, (future, future))
    assert cleanup_temp_files(tmp_path, older_than=0) == [str(ahead)]
