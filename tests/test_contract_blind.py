"""Library promises pinned after the blind mutation round."""

from __future__ import annotations

import errno
import os
import secrets
import stat
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import is_root, posix_only, windows_only

from durablewrite import (
    NO_RETRY,
    RetryPolicy,
    SharingViolationError,
    _replace,
    _write,
    atomic_write,
    write_bytes_atomic,
    write_json_atomic,
)

HOUR = 3600


def test_a_taken_temp_name_is_skipped_for_a_fresh_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    names: Iterator[str] = iter(["aaaaaaaa", "bbbbbbbb"])
    monkeypatch.setattr(secrets, "token_hex", lambda n: next(names))
    (tmp_path / ".t.aaaaaaaa.dwtmp").write_bytes(b"someone else's")
    write_bytes_atomic(tmp_path / "t", b"x")
    assert (tmp_path / "t").read_bytes() == b"x"
    assert (tmp_path / ".t.aaaaaaaa.dwtmp").read_bytes() == b"someone else's"


@posix_only
def test_a_symlink_loop_is_refused_not_replaced(tmp_path: Path) -> None:
    (tmp_path / "loop").symlink_to(tmp_path / "loop")
    with pytest.raises(OSError) as info:
        write_bytes_atomic(tmp_path / "loop", b"x")
    assert info.value.errno == errno.ELOOP and (tmp_path / "loop").is_symlink()


@posix_only
@pytest.mark.skipif(not is_root(), reason="changing the owner needs root")
def test_preserve_owner_keeps_distinct_uid_and_gid(tmp_path: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("POSIX behaviour")
    target = tmp_path / "t"
    target.write_text("old")
    os.chown(target, 1000, 2000)
    write_bytes_atomic(target, b"new", preserve_owner=True)
    assert (target.stat().st_uid, target.stat().st_gid) == (1000, 2000)


@pytest.mark.skipif(not os.path.isdir("/proc/self/fd"), reason="needs /proc")
def test_full_syncs_do_not_leak_directory_descriptors(tmp_path: Path) -> None:
    before = len(os.listdir("/proc/self/fd"))
    for i in range(50):
        write_bytes_atomic(tmp_path / "t", b"%d" % i, fsync="full")
    assert len(os.listdir("/proc/self/fd")) <= before


@posix_only
@pytest.mark.skipif(is_root(), reason="root ignores directory permissions")
def test_a_posix_permission_error_is_not_waited_out(tmp_path: Path) -> None:
    temp = tmp_path / ".t.0123abcd.dwtmp"
    temp.write_bytes(b"")
    tmp_path.chmod(0o500)
    slept: list[float] = []
    try:
        assert _replace.remove_temp(str(temp), RetryPolicy(sleep=slept.append)) is False
    finally:
        tmp_path.chmod(0o700)
    assert slept == []


def test_removing_a_temp_file_never_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_replace, "try_remove", lambda path: None)

    def broken(delay: float) -> None:
        raise RuntimeError("sleep")

    with pytest.raises(KeyError), atomic_write(tmp_path / "t", retry=RetryPolicy(sleep=broken)):
        raise KeyError("block")


def _locked(winerror: int, times: int) -> object:
    calls = {"n": 0}
    real = os.replace

    def replace(src: str, dst: str) -> None:
        calls["n"] += 1
        if calls["n"] <= times:
            raise OSError(0, "locked", src, winerror, dst)
        real(src, dst)

    return replace


@windows_only
def test_a_lock_violation_is_retried_like_a_sharing_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(os, "replace", _locked(33, 1))
    slept: list[float] = []
    write_bytes_atomic(tmp_path / "t", b"x", fsync="file", retry=RetryPolicy(sleep=slept.append))
    assert (tmp_path / "t").read_bytes() == b"x" and len(slept) == 1


@windows_only
def test_an_exhausted_lock_names_the_target_with_eacces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(os, "replace", _locked(32, 99))
    with pytest.raises(SharingViolationError) as info:
        write_bytes_atomic(tmp_path / "t", b"x", fsync="file", retry=NO_RETRY)
    assert info.value.errno == errno.EACCES and info.value.filename == str(tmp_path / "t")


@windows_only
def test_a_directory_appearing_at_the_target_is_not_retried(tmp_path: Path) -> None:
    slept: list[float] = []
    with (
        pytest.raises(PermissionError) as info,
        atomic_write(tmp_path / "t", retry=RetryPolicy(sleep=slept.append)) as f,
    ):
        f.write("x")
        (tmp_path / "t").mkdir()
    assert not isinstance(info.value, SharingViolationError) and slept == []


@posix_only
def test_write_json_passes_preserve_mode_through(tmp_path: Path) -> None:
    target = tmp_path / "c.json"
    target.write_text("{}")
    target.chmod(0o600)
    old = os.umask(0o022)
    try:
        write_json_atomic(target, {}, preserve_mode=False)
    finally:
        os.umask(old)
    assert stat.S_IMODE(target.stat().st_mode) == 0o644


def test_write_json_syncs_the_directory_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    synced: list[str] = []
    monkeypatch.setattr(_write, "fsync_directory", synced.append)
    write_json_atomic(tmp_path / "c.json", {})
    assert len(synced) == 1


def test_write_bytes_refuses_an_integer(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        write_bytes_atomic(tmp_path / "t", 3)  # type: ignore[arg-type]
    assert list(tmp_path.iterdir()) == []
