"""Command line wiring pinned after the blind mutation round."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from durablewrite import RetryPolicy, _cli, atomic_write
from durablewrite._cli import main


def _stdin(monkeypatch: pytest.MonkeyPatch, data: bytes) -> None:
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(data)))


def _captured(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Record the arguments the CLI passes to atomic_write, then let it write."""
    seen: dict[str, Any] = {}
    real = atomic_write

    def spy(path: str, mode: str, **kwargs: Any) -> Any:
        seen.update(kwargs, path=path, mode=mode)
        return real(path, mode, **kwargs)

    monkeypatch.setattr(_cli, "atomic_write", spy)
    return seen


def test_defaults_reach_the_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _captured(monkeypatch)
    _stdin(monkeypatch, b"x")
    assert main([str(tmp_path / "t")]) == 0
    assert seen["fsync"] == "full" and seen["permissions"] is None
    assert seen["follow_symlinks"] is True and seen["overwrite"] is True
    assert seen["retry"] == RetryPolicy(max_attempts=8)


def test_every_option_reaches_the_library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _captured(monkeypatch)
    _stdin(monkeypatch, b"x")
    argv = ["--fsync", "none", "--permissions", "600", "--attempts", "3"]
    argv += ["--no-follow-symlinks", "--no-overwrite", str(tmp_path / "t")]
    assert main(argv) == 0
    assert seen["fsync"] == "none" and seen["permissions"] == 0o600
    assert seen["follow_symlinks"] is False and seen["overwrite"] is False
    assert seen["retry"] == RetryPolicy(max_attempts=3) and seen["mode"] == "wb"


def test_zero_attempts_is_a_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(["--attempts", "0", str(tmp_path / "t")])
    assert info.value.code == 1
    assert "positive integer" in capsys.readouterr().err


class _Interrupted(io.BytesIO):
    def read(self, size: int | None = -1) -> bytes:
        raise KeyboardInterrupt

    def readinto(self, buffer: Any) -> int:
        raise KeyboardInterrupt


def test_an_interrupt_while_reading_exits_130_and_keeps_the_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "t"
    target.write_bytes(b"old")
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(_Interrupted()))
    assert main([str(target)]) == 130
    assert target.read_bytes() == b"old" and sorted(p.name for p in tmp_path.iterdir()) == ["t"]


def test_json_must_be_utf8(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stdin(monkeypatch, b'"\xff"')
    assert main(["--json", str(tmp_path / "j.json")]) == 1
    assert list(tmp_path.iterdir()) == []
