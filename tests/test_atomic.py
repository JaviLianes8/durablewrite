from __future__ import annotations

import os
from pathlib import Path

import pytest

from durablewrite import atomic_write, write_bytes_atomic, write_text_atomic


def test_write_text_atomic_creates_the_file(tmp_path: Path) -> None:
    target = tmp_path / "note.txt"
    write_text_atomic(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"


def test_write_bytes_atomic_creates_the_file(tmp_path: Path) -> None:
    target = tmp_path / "blob.bin"
    write_bytes_atomic(target, b"\x00\x01\x02")
    assert target.read_bytes() == b"\x00\x01\x02"


def test_write_text_atomic_uses_utf8_by_default(tmp_path: Path) -> None:
    target = tmp_path / "unicode.txt"
    write_text_atomic(target, "cafe é 中")
    assert target.read_bytes() == "cafe é 中".encode()


def test_context_manager_writes_the_full_content(tmp_path: Path) -> None:
    target = tmp_path / "doc.txt"
    with atomic_write(target) as f:
        f.write("part one ")
        f.write("part two")
    assert target.read_text(encoding="utf-8") == "part one part two"


def test_overwrite_replaces_existing_content(tmp_path: Path) -> None:
    target = tmp_path / "state.txt"
    target.write_text("old", encoding="utf-8")
    write_text_atomic(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_crash_before_replace_leaves_original_intact(tmp_path: Path) -> None:
    target = tmp_path / "state.txt"
    target.write_text("original", encoding="utf-8")
    with pytest.raises(RuntimeError), atomic_write(target) as f:
        f.write("half written")
        raise RuntimeError("boom")
    assert target.read_text(encoding="utf-8") == "original"


def test_error_removes_the_temp_file(tmp_path: Path) -> None:
    target = tmp_path / "state.txt"
    with pytest.raises(RuntimeError), atomic_write(target) as f:
        f.write("junk")
        raise RuntimeError("boom")
    leftovers = [p for p in tmp_path.iterdir() if p.name != target.name]
    assert leftovers == []


def test_success_leaves_no_temp_file(tmp_path: Path) -> None:
    target = tmp_path / "state.txt"
    write_text_atomic(target, "done")
    assert [p.name for p in tmp_path.iterdir()] == [target.name]


def test_temp_file_lives_in_the_target_directory(tmp_path: Path) -> None:
    target = tmp_path / "state.txt"
    seen: list[str] = []
    with atomic_write(target) as f:
        f.write("x")
        seen.extend(p.name for p in tmp_path.iterdir())
    assert any(name != target.name for name in seen)


def test_invalid_mode_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mode must be"), atomic_write(tmp_path / "x", "a"):
        pass


def test_encoding_in_binary_mode_is_rejected(tmp_path: Path) -> None:
    with (
        pytest.raises(ValueError, match="encoding is not allowed"),
        atomic_write(tmp_path / "x", "wb", encoding="utf-8"),
    ):
        pass


def test_binary_mode_writes_raw_bytes(tmp_path: Path) -> None:
    target = tmp_path / "raw.bin"
    with atomic_write(target, "wb") as f:
        f.write(b"line\r\nkept")
    assert target.read_bytes() == b"line\r\nkept"


def test_fsync_dir_disabled_still_writes(tmp_path: Path) -> None:
    target = tmp_path / "state.txt"
    write_text_atomic(target, "payload", fsync_dir=False)
    assert target.read_text(encoding="utf-8") == "payload"


def test_non_durable_still_writes(tmp_path: Path) -> None:
    target = tmp_path / "state.txt"
    write_text_atomic(target, "payload", durable=False, fsync_dir=False)
    assert target.read_text(encoding="utf-8") == "payload"


def test_accepts_a_string_path(tmp_path: Path) -> None:
    target = os.path.join(str(tmp_path), "str.txt")
    write_text_atomic(target, "ok")
    assert Path(target).read_text(encoding="utf-8") == "ok"


def test_newline_is_preserved_in_text_mode(tmp_path: Path) -> None:
    target = tmp_path / "nl.txt"
    write_text_atomic(target, "a\nb", newline="")
    assert target.read_bytes() == b"a\nb"
