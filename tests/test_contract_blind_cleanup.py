"""cleanup_temp_files promises pinned after the blind mutation round."""

from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest
from conftest import posix_only, windows_only

from durablewrite import cleanup_temp_files

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
