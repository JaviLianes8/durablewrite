"""Hostile targets and interruptions found by the adversarial review."""

from __future__ import annotations

import errno
import io
import os
import stat
import sys
from pathlib import Path

import pytest
from conftest import posix_only, windows_only

from durablewrite import RetryPolicy, _write, atomic_write, write_text_atomic
from durablewrite._cli import main


@posix_only
def test_a_fifo_target_is_refused_and_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if sys.platform == "win32":
        pytest.skip("POSIX behaviour")
    fifo = tmp_path / "f"
    os.mkfifo(fifo)
    with pytest.raises(OSError) as info:
        write_text_atomic(fifo, "x")
    assert info.value.errno == errno.EINVAL
    assert stat.S_ISFIFO(os.lstat(fifo).st_mode) and os.listdir(tmp_path) == ["f"]
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"x")))
    assert main(["--append", str(fifo)]) == 1
    assert stat.S_ISFIFO(os.lstat(fifo).st_mode) and os.listdir(tmp_path) == ["f"]


@posix_only
def test_permission_bits_are_set_through_the_descriptor_not_the_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def by_name(*args: object, **kwargs: object) -> None:
        raise AssertionError("chmod by name follows a swapped symlink")

    monkeypatch.setattr(os, "chmod", by_name)
    (tmp_path / "keep").write_text("old")
    write_text_atomic(tmp_path / "t", "x", permissions=0o640)
    write_text_atomic(tmp_path / "keep", "new")
    assert stat.S_IMODE(os.stat(tmp_path / "t").st_mode) == 0o640


def test_a_codec_that_is_not_a_text_encoding_is_refused_up_front(tmp_path: Path) -> None:
    for codec in ("hex", "rot13"):
        with pytest.raises(LookupError, match="text encoding"):
            atomic_write(tmp_path / "t", encoding=codec)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("error", [RuntimeError, KeyboardInterrupt])
def test_a_failing_wrapper_closes_the_descriptor_once_and_keeps_its_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: type[BaseException]
) -> None:
    def broken(*args: object, **kwargs: object) -> None:
        raise error("wrapper")

    monkeypatch.setattr(io, "TextIOWrapper", broken)
    with pytest.raises(error, match="wrapper"), atomic_write(tmp_path / "t"):
        pass
    assert list(tmp_path.iterdir()) == []


def test_an_interrupt_before_the_temp_file_is_wrapped_still_removes_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupted(fd: int, plan: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(_write, "_open", interrupted)
    with pytest.raises(KeyboardInterrupt), atomic_write(tmp_path / "t"):
        pass
    assert list(tmp_path.iterdir()) == []


def test_cli_json_accepts_integers_longer_than_int_conversion_allows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = ("[" + "9" * 5000 + ", 1.5e999]").encode()
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(payload)))
    assert main(["--json", str(tmp_path / "j.json")]) == 0
    assert (tmp_path / "j.json").read_bytes() == payload


@windows_only
def test_an_alternate_data_stream_name_is_refused_on_windows(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="data stream"):
        write_text_atomic(str(tmp_path / "file.txt") + ":stream", "x")
    assert list(tmp_path.iterdir()) == []


def test_retry_delays_longer_than_a_day_are_refused() -> None:
    with pytest.raises(ValueError, match="at most"):
        RetryPolicy(max_delay=1e300)
    with pytest.raises(ValueError, match="at most"):
        RetryPolicy(initial_delay=86401)
    assert RetryPolicy(max_delay=86400).max_delay == 86400
