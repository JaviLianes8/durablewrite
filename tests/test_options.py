from __future__ import annotations

from pathlib import Path

import pytest

from durablewrite import DEFAULT_RETRY, NO_RETRY, RetryPolicy, atomic_write, write_text_atomic


def test_default_retry_delays_back_off_and_cap() -> None:
    assert list(DEFAULT_RETRY.delays()) == [0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.5]
    assert sum(DEFAULT_RETRY.delays()) < 1.2


def test_no_retry_has_no_delays() -> None:
    assert list(NO_RETRY.delays()) == []


def test_custom_policy_delays() -> None:
    policy = RetryPolicy(max_attempts=4, initial_delay=0.1, multiplier=3, max_delay=0.5)
    assert list(policy.delays()) == pytest.approx([0.1, 0.3, 0.5])


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_attempts": 0}, "max_attempts"),
        ({"initial_delay": -1}, "negative"),
        ({"max_delay": -1}, "negative"),
        ({"multiplier": 0.5}, "multiplier"),
    ],
)
def test_invalid_policy_is_rejected(kwargs: dict[str, float], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        RetryPolicy(**kwargs)  # type: ignore[arg-type]


def test_policies_compare_by_value_ignoring_sleep() -> None:
    assert RetryPolicy(sleep=lambda _: None) == DEFAULT_RETRY


@pytest.mark.parametrize("level", ["none", "file", "full"])
def test_every_fsync_level_writes_the_content(tmp_path: Path, level: str) -> None:
    target = tmp_path / "f.txt"
    write_text_atomic(target, level, fsync=level)  # type: ignore[arg-type]
    assert target.read_text(encoding="utf-8") == level


def test_legacy_flags_still_work(tmp_path: Path) -> None:
    target = tmp_path / "f.txt"
    write_text_atomic(target, "legacy", durable=False, fsync_dir=True)
    assert target.read_text(encoding="utf-8") == "legacy"


def test_unknown_fsync_level_is_rejected_before_touching_disk(tmp_path: Path) -> None:
    with (
        pytest.raises(ValueError, match="fsync must be"),
        atomic_write(tmp_path / "f.txt", fsync="always"),  # type: ignore[call-overload]
    ):
        pass
    assert list(tmp_path.iterdir()) == []
