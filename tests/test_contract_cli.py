"""Command line message limits and the exit-3 warning, on every platform."""

from __future__ import annotations

import errno
import io
from pathlib import Path

import pytest

from durablewrite import _write
from durablewrite._cli import _cut, main


def test_messages_are_cut_exactly_past_120_characters() -> None:
    assert _cut("a" * 120) == "a" * 120
    assert _cut("b" * 121) == "b" * 117 + "..."
    assert _cut("") == ""


def test_an_unsynced_directory_gives_status_3_and_a_cut_warning_naming_the_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(directory: str) -> None:
        raise PermissionError(errno.EACCES, "Permission denied", directory)

    monkeypatch.setattr(_write, "fsync_directory", refuse)
    for name, cut in (("t", False), ("w" * 150, True)):
        target = tmp_path / name
        monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"data")))
        assert main([str(target)]) == 3
        line = capsys.readouterr().err.splitlines()[-1]
        prefix = "durablewrite: warning: "
        assert line.startswith(prefix + str(target)[:60])
        message = line[len(prefix) :]
        assert len(message) <= 120 and (message.endswith("...") or not cut)
        assert target.read_bytes() == b"data"
