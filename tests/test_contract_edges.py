"""Edge promises pinned after the author mutation round."""

from __future__ import annotations

import errno
import io
import os
import stat
import sys
from pathlib import Path

import pytest
from conftest import can_symlink, is_root, posix_only

from durablewrite import (
    DirectorySyncError,
    RetryPolicy,
    _write,
    atomic_write,
    cleanup_temp_files,
    write_text_atomic,
)
from durablewrite._cli import main


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_text_mode_defaults_to_utf8_whatever_the_locale(tmp_path: Path) -> None:
    with atomic_write(tmp_path / "t") as f:
        f.write("café ☃")
    assert (tmp_path / "t").read_bytes() == "café ☃".encode()


def test_create_only_refuses_a_dangling_link_before_the_block(tmp_path: Path) -> None:
    if not can_symlink(tmp_path):
        pytest.skip("symlinks are not available to this user")
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "missing")
    with pytest.raises(FileExistsError):
        atomic_write(link, overwrite=False, follow_symlinks=False).__enter__()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["link"]


@pytest.mark.parametrize(
    ("durable", "fsync_dir", "dir_syncs"), [(True, False, 0), (False, True, 1)]
)
def test_legacy_flags_choose_the_file_and_directory_syncs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, durable: bool, fsync_dir: bool, dir_syncs: int
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(_write, "fsync_directory", calls.append)
    monkeypatch.setattr(_write, "sync_fd", lambda fd: calls.append("file"))
    write_text_atomic(tmp_path / "t", "x", durable=durable, fsync_dir=fsync_dir)
    assert calls.count("file") == int(durable)
    assert len(calls) - calls.count("file") == dir_syncs


def test_the_first_delay_is_capped_too() -> None:
    assert list(RetryPolicy(max_attempts=3, initial_delay=2, max_delay=0.5).delays()) == [0.5, 0.5]


@pytest.mark.parametrize("length", [1, 30, 48])
def test_names_up_to_48_characters_appear_whole_in_the_temp_name(
    tmp_path: Path, length: int
) -> None:
    name = "n" * length
    with atomic_write(tmp_path / name) as f:
        f.write("x")
        temps = [p.name for p in tmp_path.iterdir() if p.name != name]
    assert len(temps) == 1 and temps[0].startswith(f".{name}.")


def test_cleanup_respects_the_exact_age_boundary(tmp_path: Path) -> None:
    stale = tmp_path / ".t.0123abcd.dwtmp"
    stale.write_bytes(b"")
    os.utime(stale, (1_000_000, 1_000_000))
    assert cleanup_temp_files(tmp_path, older_than=10.5, now=1_000_010) == []
    assert cleanup_temp_files(tmp_path, older_than=10, now=1_000_010) == [str(stale)]


def test_cleanup_never_follows_a_link_named_like_a_temp_file(tmp_path: Path) -> None:
    if not can_symlink(tmp_path):
        pytest.skip("symlinks are not available to this user")
    (tmp_path / "real").write_bytes(b"keep")
    (tmp_path / ".t.0123abcd.dwtmp").symlink_to(tmp_path / "real")
    assert cleanup_temp_files(tmp_path, older_than=0) == []
    assert (tmp_path / ".t.0123abcd.dwtmp").is_symlink()


@posix_only
def test_new_files_take_every_bit_the_umask_allows(tmp_path: Path) -> None:
    old = os.umask(0o002)
    try:
        write_text_atomic(tmp_path / "t", "x")
    finally:
        os.umask(old)
    assert _mode(tmp_path / "t") == 0o664


@posix_only
def test_a_replaced_link_does_not_inherit_the_mode_of_its_target(tmp_path: Path) -> None:
    (tmp_path / "real").write_text("x")
    (tmp_path / "real").chmod(0o600)
    (tmp_path / "link").symlink_to(tmp_path / "real")
    old = os.umask(0o022)
    try:
        write_text_atomic(tmp_path / "link", "y", follow_symlinks=False)
    finally:
        os.umask(old)
    assert _mode(tmp_path / "link") == 0o644 and _mode(tmp_path / "real") == 0o600


@posix_only
@pytest.mark.skipif(not is_root(), reason="changing the owner needs root")
def test_preserve_owner_restores_another_users_file(tmp_path: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("POSIX behaviour")
    target = tmp_path / "owned"
    target.write_text("old")
    os.chown(target, 65534, 65534)
    write_text_atomic(target, "new", preserve_owner=True)
    assert (target.stat().st_uid, target.stat().st_gid) == (65534, 65534)
    write_text_atomic(target, "newer")
    assert target.stat().st_uid == os.geteuid()


def test_cli_accepts_special_permission_bits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"x")))
    assert main(["--permissions", "1644", str(tmp_path / "t")]) == 0
    os.chmod(tmp_path / "t", 0o644)


@posix_only
@pytest.mark.skipif(is_root(), reason="root reads anything")
def test_cli_append_fails_when_the_current_content_cannot_be_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "t"
    target.write_bytes(b"precious")
    target.chmod(0o200)
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"more")))
    try:
        assert main(["--append", str(target)]) == 1
    finally:
        target.chmod(0o600)
    assert target.read_bytes() == b"precious"


def _last_error(capsys: pytest.CaptureFixture[str]) -> str:
    line = capsys.readouterr().err.splitlines()[-1]
    assert line.startswith("durablewrite: error: ")
    return line[len("durablewrite: error: ") :]


def test_cli_error_messages_are_cut_to_120_characters(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for argv in (["--fsync", "x" * 300, "t"], ["--" + "y" * 300, "t"]):
        with pytest.raises(SystemExit) as info:
            main(argv)
        assert info.value.code == 1
        message = _last_error(capsys)
        assert len(message) == 120 and message.endswith("...")
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"x")))
    assert main([str(tmp_path / ("m" * 150) / "t")]) == 1
    message = _last_error(capsys)
    assert len(message) == 120 and message.endswith("...")
    with pytest.raises(SystemExit):
        main(["--fsync", "nope", str(tmp_path / "t")])
    assert not _last_error(capsys).endswith("...")


def test_a_directory_sync_error_names_the_directory_once_and_keeps_the_errno(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(directory: str) -> None:
        raise PermissionError(errno.EACCES, "Permission denied", directory)

    monkeypatch.setattr(_write, "fsync_directory", refuse)
    with pytest.raises(DirectorySyncError) as info:
        write_text_atomic(tmp_path / "t", "x")
    error = info.value
    assert error.errno == errno.EACCES and error.filename == str(tmp_path)
    assert str(error).count(tmp_path.name) == 1 and "Permission denied" in str(error)
    assert isinstance(error.__cause__, PermissionError)
    assert (tmp_path / "t").read_text(encoding="utf-8") == "x"


@pytest.mark.parametrize("name", ["durable", "fsync_dir", "overwrite", "follow_symlinks"])
def test_flag_errors_name_the_option_even_when_fsync_is_given(tmp_path: Path, name: str) -> None:
    with pytest.raises(TypeError, match=name):
        write_text_atomic(tmp_path / "t", "x", fsync="full", **{name: "yes"})  # type: ignore[arg-type]
    assert list(tmp_path.iterdir()) == []
