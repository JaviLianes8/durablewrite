from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from conftest import leftovers

from durablewrite import cleanup_temp_files, write_json_atomic


def test_json_is_written_with_a_trailing_lf_newline(tmp_path: Path) -> None:
    target = tmp_path / "config.json"
    write_json_atomic(target, {"name": "café", "items": [1, 2]})
    raw = target.read_bytes()
    assert raw.endswith(b"]\n}\n")
    assert b"\r" not in raw
    assert "café".encode() in raw
    assert json.loads(raw) == {"name": "café", "items": [1, 2]}


def test_json_options_are_passed_through(tmp_path: Path) -> None:
    target = tmp_path / "c.json"
    write_json_atomic(target, {"b": 1, "a": "é"}, indent=None, sort_keys=True, ensure_ascii=True)
    assert target.read_text(encoding="utf-8") == '{"a": "\\u00e9", "b": 1}\n'


def test_json_default_hook_is_used(tmp_path: Path) -> None:
    target = tmp_path / "c.json"
    write_json_atomic(target, {"path": Path("x")}, default=str)
    assert json.loads(target.read_text(encoding="utf-8")) == {"path": "x"}


def test_unencodable_json_touches_nothing(tmp_path: Path) -> None:
    target = tmp_path / "c.json"
    target.write_text("{}", encoding="utf-8")
    with pytest.raises(TypeError):
        write_json_atomic(target, {"x": object()})
    assert target.read_text(encoding="utf-8") == "{}"
    assert leftovers(tmp_path, target.name) == []


def _stale(directory: Path, name: str, age: float) -> Path:
    path = directory / name
    path.write_bytes(b"partial")
    stamp = time.time() - age
    os.utime(path, (stamp, stamp))
    return path


def test_cleanup_removes_only_old_temp_files(tmp_path: Path) -> None:
    old = _stale(tmp_path, ".a.txt.0123abcd.dwtmp", 7200)
    _stale(tmp_path, ".a.txt.89abcdef.dwtmp", 10)
    assert cleanup_temp_files(tmp_path) == [str(old)]
    assert leftovers(tmp_path, "") == [".a.txt.89abcdef.dwtmp"]


def test_cleanup_never_touches_other_files(tmp_path: Path) -> None:
    names = [
        "a.txt",
        ".a.txt.0123abcd.tmp",
        "a.txt.0123abcd.dwtmp",
        ".a.txt.0123ABCD.dwtmp",
        ".a.txt.0123abc.dwtmp",
        ".a.txt.0123abcd.dwtmp.bak",
    ]
    for name in names:
        _stale(tmp_path, name, 7200)
    (tmp_path / ".dir.0123abcd.dwtmp").mkdir()
    assert cleanup_temp_files(tmp_path, older_than=0) == []
    assert len(list(tmp_path.iterdir())) == len(names) + 1


def test_cleanup_can_target_one_file(tmp_path: Path) -> None:
    mine = _stale(tmp_path, ".a.txt.0123abcd.dwtmp", 7200)
    _stale(tmp_path, ".b.txt.0123abcd.dwtmp", 7200)
    assert cleanup_temp_files(tmp_path, target=tmp_path / "a.txt") == [str(mine)]


def test_cleanup_uses_the_given_clock(tmp_path: Path) -> None:
    path = _stale(tmp_path, ".a.txt.0123abcd.dwtmp", 0)
    assert cleanup_temp_files(tmp_path, older_than=60) == []
    assert cleanup_temp_files(tmp_path, older_than=60, now=time.time() + 120) == [str(path)]


def test_cleanup_rejects_a_negative_age(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="negative"):
        cleanup_temp_files(tmp_path, older_than=-1)
