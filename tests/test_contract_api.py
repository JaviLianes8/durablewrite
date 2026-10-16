"""Argument checks, error types and messages: everything is refused before any I/O."""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import pytest

from durablewrite import (
    DEFAULT_RETRY,
    RetryPolicy,
    atomic_write,
    cleanup_temp_files,
    write_bytes_atomic,
    write_json_atomic,
    write_text_atomic,
)

HUGE = "x" * 100_000


def _refused(tmp_path: Path, error: type[Exception], **kwargs: Any) -> str:
    kwargs_names = set(kwargs)
    target = kwargs.pop("path", tmp_path / "t")
    mode = kwargs.pop("mode", "w")
    with pytest.raises(error) as info:
        atomic_write(target, mode, **kwargs)
    assert list(tmp_path.iterdir()) == [], "nothing may be touched"
    message = str(info.value)
    assert len(message) < 100 and HUGE[:50] not in message
    if "path" in kwargs_names:
        assert "path" in message
    return message


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"mode": "a"}, ValueError),
        ({"mode": HUGE}, ValueError),
        ({"mode": "wb", "encoding": "utf-8"}, ValueError),
        ({"mode": "wb", "newline": ""}, ValueError),
        ({"encoding": "no-such-codec"}, LookupError),
        ({"encoding": 8}, TypeError),
        ({"newline": "\t"}, ValueError),
        ({"newline": 1}, TypeError),
        ({"fsync": "always"}, ValueError),
        ({"fsync": HUGE}, ValueError),
        ({"fsync": ["full"]}, TypeError),
        ({"fsync": 3}, TypeError),
        ({"mode": 5}, TypeError),
        ({"overwrite": "no"}, TypeError),
        ({"follow_symlinks": "false"}, TypeError),
        ({"preserve_mode": []}, TypeError),
        ({"preserve_owner": 1}, TypeError),
        ({"durable": 0}, TypeError),
        ({"fsync_dir": None}, TypeError),
        ({"permissions": 0o10000}, ValueError),
        ({"permissions": -1}, ValueError),
        ({"permissions": True}, TypeError),
        ({"permissions": "644"}, TypeError),
        ({"permissions": 6.0}, TypeError),
        ({"retry": 3}, TypeError),
        ({"path": b"t"}, TypeError),
        ({"path": 3}, TypeError),
        ({"path": ""}, ValueError),
        ({"path": "a\x00b"}, ValueError),
    ],
)
def test_bad_arguments_raise_at_call_time_with_short_messages(
    tmp_path: Path, kwargs: dict[str, Any], error: type[Exception]
) -> None:
    _refused(tmp_path, error, **kwargs)


def test_a_path_ending_with_a_separator_does_not_echo_the_path(tmp_path: Path) -> None:
    message = _refused(tmp_path, ValueError, path=str(tmp_path / HUGE[:200]) + os.sep)
    assert "separator" in message


@pytest.mark.parametrize("permissions", [0, 0o644, 0o7777])
def test_permission_bits_at_the_limits_are_accepted(tmp_path: Path, permissions: int) -> None:
    write_bytes_atomic(tmp_path / "t", b"x", permissions=permissions)
    os.chmod(tmp_path / "t", 0o644)
    assert (tmp_path / "t").read_bytes() == b"x"


@pytest.mark.parametrize("newline", [None, "", "\n", "\r", "\r\n"])
def test_every_newline_open_accepts_is_accepted(tmp_path: Path, newline: str | None) -> None:
    write_text_atomic(tmp_path / "t", "a\nb", newline=newline)
    expected = {None: os.linesep, "": "\n"}.get(newline, newline)
    assert (tmp_path / "t").read_bytes() == f"a{expected}b".encode()


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"max_attempts": 0}, ValueError),
        ({"max_attempts": 1.5}, TypeError),
        ({"max_attempts": True}, TypeError),
        ({"initial_delay": math.nan}, ValueError),
        ({"initial_delay": math.inf}, ValueError),
        ({"initial_delay": -0.1}, ValueError),
        ({"initial_delay": "0.1"}, TypeError),
        ({"max_delay": math.nan}, ValueError),
        ({"max_delay": -1}, ValueError),
        ({"multiplier": 0.99}, ValueError),
        ({"multiplier": math.inf}, ValueError),
        ({"multiplier": 10**400}, ValueError),
        ({"sleep": None}, TypeError),
    ],
)
def test_retry_policy_rejects_values_that_cannot_wait(
    kwargs: dict[str, Any], error: type[Exception]
) -> None:
    with pytest.raises(error):
        RetryPolicy(**kwargs)


def test_retry_delays_are_floats_capped_even_for_huge_budgets() -> None:
    policy = RetryPolicy(max_attempts=5000, initial_delay=1, multiplier=10, max_delay=2)
    delays = list(policy.delays())
    assert len(delays) == 4999 and max(delays) == 2.0
    assert all(type(d) is float for d in delays)
    assert RetryPolicy(max_attempts=2, initial_delay=0, max_delay=0).max_attempts == 2
    assert RetryPolicy(8, 0.01, 2.0, 0.5) == DEFAULT_RETRY


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"older_than": math.nan}, ValueError),
        ({"older_than": -1}, ValueError),
        ({"older_than": math.inf}, ValueError),
        ({"older_than": True}, TypeError),
        ({"now": math.nan}, ValueError),
        ({"now": "now"}, TypeError),
        ({"target": b"t"}, TypeError),
    ],
)
def test_cleanup_rejects_ages_that_would_remove_live_temp_files(
    tmp_path: Path, kwargs: dict[str, Any], error: type[Exception]
) -> None:
    live = tmp_path / ".t.0123abcd.dwtmp"
    live.write_bytes(b"in flight")
    with pytest.raises(error):
        cleanup_temp_files(tmp_path, **kwargs)
    assert live.exists()


def test_cleanup_rejects_bytes_directories_and_reports_missing_ones(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        cleanup_temp_files(os.fsencode(tmp_path))  # type: ignore[arg-type]
    with pytest.raises(FileNotFoundError):
        cleanup_temp_files(tmp_path / "missing")


def test_helpers_check_their_arguments_the_same_way(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_text_atomic(tmp_path / "t", "x", fsync="sometimes")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        write_bytes_atomic(tmp_path / "t", b"x", permissions="600")  # type: ignore[arg-type]
    with pytest.raises(LookupError):
        write_text_atomic(tmp_path / "t", "x", encoding="nope")
    with pytest.raises(TypeError):
        write_json_atomic(tmp_path / "t", {1, 2})
    assert list(tmp_path.iterdir()) == []
