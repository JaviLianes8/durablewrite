"""A relative target is pinned when the write starts, whatever happens to the cwd."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from durablewrite import _write, atomic_write


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
