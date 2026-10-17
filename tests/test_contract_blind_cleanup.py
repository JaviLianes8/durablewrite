"""cleanup_temp_files promises pinned after the blind mutation round."""

from __future__ import annotations

import errno
import hashlib
import os
from pathlib import Path

import pytest
from conftest import posix_only, windows_only

from durablewrite import RetryPolicy, atomic_write, cleanup_temp_files

HOUR = 3600


def test_cleanup_does_not_report_a_file_someone_else_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".t.0123abcd.dwtmp").write_bytes(b"")
    real = os.remove

    def raced(path: str) -> None:
        real(path)
        raise FileNotFoundError(errno.ENOENT, "gone", path)

    monkeypatch.setattr(os, "remove", raced)
    assert cleanup_temp_files(tmp_path, older_than=0) == []


def test_cleanup_defaults_to_one_hour_and_exact_names(tmp_path: Path) -> None:
    young = tmp_path / ".t.0123abcd.dwtmp"
    other = tmp_path / ".x.0123456789.dwtmp"
    for path in (young, other):
        path.write_bytes(b"")
        os.utime(path, (1_000_000, 1_000_000))
    assert cleanup_temp_files(tmp_path, now=1_000_000 + 120) == []
    assert cleanup_temp_files(tmp_path, now=1_000_000 + HOUR) == [str(young)]
    assert other.exists()
    assert cleanup_temp_files(tmp_path, now=-1.0) == []


def test_cleanup_returns_sorted_paths(tmp_path: Path) -> None:
    for i in range(40):
        (tmp_path / f".t{(i * 7919) % 97}.0123abcd.dwtmp").write_bytes(b"")
    removed = cleanup_temp_files(tmp_path, older_than=0)
    assert removed == sorted(removed) and len(removed) == 40


@windows_only
def test_cleanup_does_not_report_a_temp_file_still_held_open(tmp_path: Path) -> None:
    temp = tmp_path / ".t.0123abcd.dwtmp"
    with open(temp, "wb"):
        assert cleanup_temp_files(tmp_path, older_than=0) == []
    assert temp.exists()


@posix_only
def test_cleanup_matches_names_with_a_newline(tmp_path: Path) -> None:
    odd = tmp_path / ".a\nb.0123abcd.dwtmp"
    odd.write_bytes(b"")
    assert cleanup_temp_files(tmp_path, older_than=0) == [str(odd)]


@posix_only  # Windows cannot delete the temp file while the writer holds it open
def test_a_temp_file_already_gone_is_not_waited_for(tmp_path: Path) -> None:
    slept: list[float] = []
    with (
        pytest.raises(KeyError),
        atomic_write(tmp_path / "t", retry=RetryPolicy(sleep=slept.append)),
    ):
        for name in os.listdir(tmp_path):
            os.remove(tmp_path / name)
        raise KeyError("block")
    assert slept == [] and list(tmp_path.iterdir()) == []


@windows_only
def test_a_read_only_temp_removed_by_someone_else_is_not_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".t.0123abcd.dwtmp").write_bytes(b"")
    real = os.remove
    calls = {"n": 0}

    def raced(path: str) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            real(path)
            raise PermissionError(13, "denied", path, 5)
        real(path)

    monkeypatch.setattr(os, "remove", raced)
    assert cleanup_temp_files(tmp_path, older_than=0) == []


def test_long_names_get_the_stable_hashed_stem(tmp_path: Path) -> None:
    name = "n" * 60
    digest = hashlib.sha256(name.encode()).hexdigest()[:8]
    stale = tmp_path / f".{name[:39]}~{digest}.0123abcd.dwtmp"
    stale.write_bytes(b"")
    assert cleanup_temp_files(tmp_path, older_than=0, target=name) == [str(stale)]
