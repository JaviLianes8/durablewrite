"""What each fsync level asks of the operating system, per platform."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import IO, Any

import pytest
from conftest import windows_only

from durablewrite import _fs, _win, atomic_write, cleanup_temp_files, write_bytes_atomic


class _FakeFcntl:
    F_FULLFSYNC = 51

    def __init__(self, fail: bool) -> None:
        self.calls: list[tuple[int, int]] = []
        self.fail = fail

    def fcntl(self, fd: int, command: int) -> int:
        self.calls.append((fd, command))
        if self.fail:
            raise OSError(45, "not supported")
        return 0


@pytest.mark.parametrize("fail", [False, True])
def test_full_fsync_is_used_where_the_platform_has_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, fail: bool
) -> None:
    fake = _FakeFcntl(fail)
    synced: list[int] = []
    monkeypatch.setattr(_fs, "_fcntl", fake)
    monkeypatch.setattr(os, "fsync", synced.append)
    with open(tmp_path / "f", "wb") as f:
        _fs.sync_fd(f.fileno())
        assert fake.calls == [(f.fileno(), 51)]
        assert synced == ([f.fileno()] if fail else [])


def test_without_full_fsync_a_plain_fsync_is_made(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    synced: list[int] = []
    monkeypatch.setattr(_fs, "_fcntl", None)
    monkeypatch.setattr(os, "fsync", synced.append)
    with open(tmp_path / "f", "wb") as f:
        _fs.sync_fd(f.fileno())
        assert synced == [f.fileno()]


@pytest.mark.parametrize(
    ("level", "overwrite", "flags"),
    [("full", True, 9), ("full", False, 8), ("file", True, None), ("none", False, None)],
)
@windows_only
def test_only_full_writes_the_rename_through_on_windows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, level: str, overwrite: bool, flags: int | None
) -> None:
    seen: list[int] = []
    real = _win.move_file_ex

    def spy(src: str, dst: str, value: int) -> None:
        seen.append(value)
        real(src, dst, value)

    monkeypatch.setattr(_win, "move_file_ex", spy)
    write_bytes_atomic(tmp_path / "t", b"x", fsync=level, overwrite=overwrite)  # type: ignore[arg-type]
    assert seen == ([] if flags is None else [flags])
    assert (tmp_path / "t").read_bytes() == b"x"


@windows_only
def test_write_through_errors_look_like_os_replace_errors(tmp_path: Path) -> None:
    (tmp_path / "t").write_bytes(b"old")
    (tmp_path / "s").write_bytes(b"new")
    with pytest.raises(FileExistsError) as taken:
        _win.move_file_ex(str(tmp_path / "s"), str(tmp_path / "t"), _win.MOVEFILE_WRITE_THROUGH)
    assert getattr(taken.value, "winerror", None) == 183
    assert (tmp_path / "t").read_bytes() == b"old"
    with pytest.raises(FileNotFoundError) as missing:
        _win.move_file_ex(str(tmp_path / "missing"), str(tmp_path / "u"), 9)
    assert missing.value.filename == str(tmp_path / "missing")
    assert missing.value.filename2 == str(tmp_path / "u")
    assert getattr(missing.value, "winerror", None) == 2


@windows_only
def test_cleanup_removes_a_read_only_temp_file(tmp_path: Path) -> None:
    stale = tmp_path / ".t.0123abcd.dwtmp"
    stale.write_bytes(b"x")
    os.chmod(stale, stat.S_IREAD)
    assert cleanup_temp_files(tmp_path, older_than=0) == [str(stale)]


def test_the_stream_type_follows_the_mode(tmp_path: Path) -> None:
    with atomic_write(tmp_path / "a") as text:
        typed_text: IO[str] = text
        typed_text.write("x")
    with atomic_write(tmp_path / "b", "wb") as raw:
        typed_raw: IO[bytes] = raw
        typed_raw.write(b"x")
    mode: str = "wb"
    with atomic_write(tmp_path / "c", mode) as either:
        untyped: IO[Any] = either
        untyped.write(b"x")
    assert sorted(p.read_bytes() for p in tmp_path.iterdir()) == [b"x"] * 3
