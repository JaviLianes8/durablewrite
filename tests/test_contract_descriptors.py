"""Descriptors, special files and mode bits pinned after the second adversarial round."""

from __future__ import annotations

import errno
import io
import os
import socket
import stat
import sys
from pathlib import Path

import pytest
from conftest import posix_only, windows_only

from durablewrite import atomic_write, write_bytes_atomic, write_text_atomic


def _spy_closes(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    closed: list[int] = []
    real = os.close

    def spy(fd: int) -> None:
        closed.append(fd)
        real(fd)

    monkeypatch.setattr(os, "close", spy)
    return closed


@pytest.mark.parametrize("mode", ["w", "wb"])
def test_a_write_never_closes_the_temp_descriptor_by_number(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    closed = _spy_closes(monkeypatch)
    for _ in range(3):
        with atomic_write(tmp_path / "t", mode, fsync="file") as f:
            f.write("x" if mode == "w" else b"x")
    assert closed == [], "the file object owns the descriptor and closes it once"


def test_a_failing_wrapper_closes_the_descriptor_exactly_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed = _spy_closes(monkeypatch)

    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError("wrapper")

    monkeypatch.setattr(io, "TextIOWrapper", broken)
    with pytest.raises(RuntimeError), atomic_write(tmp_path / "t"):
        pass
    assert closed == [] and list(tmp_path.iterdir()) == []


@pytest.mark.skipif(not os.path.isdir("/proc/self/fd"), reason="needs /proc")
def test_writes_do_not_leak_descriptors(tmp_path: Path) -> None:
    before = len(os.listdir("/proc/self/fd"))
    for i in range(300):
        write_text_atomic(tmp_path / "t", str(i), fsync="none")
    assert len(os.listdir("/proc/self/fd")) <= before


@posix_only
def test_a_socket_target_is_refused_and_kept(tmp_path: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("POSIX behaviour")
    path = tmp_path / "s"
    server = socket.socket(socket.AF_UNIX)
    try:
        server.bind(str(path))
        with pytest.raises(OSError) as info:
            write_bytes_atomic(path, b"x")
        assert info.value.errno == errno.EINVAL
        assert stat.S_ISSOCK(os.lstat(path).st_mode) and os.listdir(tmp_path) == ["s"]
    finally:
        server.close()


@windows_only
def test_the_nul_device_is_refused_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(OSError) as info:
        write_text_atomic("NUL", "x")
    assert info.value.errno == errno.EINVAL and list(tmp_path.iterdir()) == []


@windows_only
def test_a_drive_relative_name_is_not_mistaken_for_a_stream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    drive = os.path.splitdrive(str(tmp_path))[0]
    write_text_atomic(drive + "t", "x")
    assert (tmp_path / "t").read_text() == "x"


@posix_only
def test_preserve_mode_keeps_setgid_and_sticky_bits(tmp_path: Path) -> None:
    target = tmp_path / "t"
    target.write_text("old")
    try:
        target.chmod(0o3750)
    except PermissionError:
        pytest.skip("this filesystem refuses special bits")
    if stat.S_IMODE(target.stat().st_mode) != 0o3750:
        pytest.skip("this filesystem drops special bits")
    write_text_atomic(target, "new")
    assert stat.S_IMODE(target.stat().st_mode) == 0o3750
