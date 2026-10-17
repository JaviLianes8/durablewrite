"""Seeded random use: operation sequences, hostile names, JSON and the CLI.

Every case derives from SEED, so a failure names the seed that reproduces it.
"""

from __future__ import annotations

import io
import json
import os
import random
import string
import time
from pathlib import Path
from typing import Any

import pytest

from durablewrite import (
    FsyncLevel,
    atomic_write,
    cleanup_temp_files,
    write_bytes_atomic,
    write_json_atomic,
    write_text_atomic,
)
from durablewrite._cli import main

SEED = int(os.environ.get("DURABLEWRITE_FUZZ_SEED", "20261016"))
LEVELS: list[FsyncLevel] = ["none", "file", "full"]
FORBIDDEN = set('<>:"/\\|?*') if os.name == "nt" else {"/"}


def test_random_operation_sequences_keep_the_model(tmp_path: Path) -> None:
    rng = random.Random(SEED)
    target = tmp_path / "state"
    model: bytes | None = None
    for step in range(300):
        data = rng.randbytes(rng.choice([0, 1, 100, 5000, 70000]))
        overwrite = rng.random() < 0.8
        fails = rng.random() < 0.2
        level = rng.choice(LEVELS)
        context = f"seed={SEED} step={step}"
        try:
            with atomic_write(target, "wb", overwrite=overwrite, fsync=level) as f:
                f.write(data[: len(data) // 2])
                if fails:
                    raise RuntimeError("stop")
                f.write(data[len(data) // 2 :])
        except FileExistsError:
            assert not overwrite and model is not None, context
        except RuntimeError:
            assert fails, context
        else:
            assert overwrite or model is None, context
            model = data
        assert (target.read_bytes() if target.exists() else None) == model, context
        assert os.listdir(tmp_path) == ([] if model is None else ["state"]), context


def _name(rng: random.Random) -> str:
    pool = string.ascii_letters + string.digits + " .-_~'!&()[]{}#%" + "é中\U0001f600☃"
    while True:
        name = "".join(rng.choice(pool) for _ in range(rng.randint(1, 60)))
        name = name.strip(" .") if os.name == "nt" else name
        if name and name not in (".", "..") and not FORBIDDEN & set(name):
            return name


def test_hostile_names_round_trip_and_are_cleaned_exactly(tmp_path: Path) -> None:
    rng = random.Random(SEED + 1)
    names = {_name(rng) for _ in range(150)}
    if os.name == "nt":
        names = {n for n in names if n.lower() not in {m.lower() for m in names if m != n}}
    for name in sorted(names):
        write_text_atomic(tmp_path / name, name)
        assert (tmp_path / name).read_text(encoding="utf-8") == name
        assert cleanup_temp_files(tmp_path, older_than=0, target=name) == []
    assert sorted(os.listdir(tmp_path)) == sorted(names)


def test_the_longest_names_the_filesystem_takes_still_work(tmp_path: Path) -> None:
    for char, count in (("a", 255), ("é", 127), ("\U0001f600", 63)):
        name = char * count
        try:
            write_bytes_atomic(tmp_path / name, b"x")
        except OSError as exc:  # the name itself is too long for this filesystem
            assert not (tmp_path / name).exists(), exc
            continue
        assert (tmp_path / name).read_bytes() == b"x"
    assert all(not n.endswith(".dwtmp") for n in os.listdir(tmp_path))


def _json_value(rng: random.Random, depth: int = 0) -> Any:
    kind = rng.randrange(7 if depth < 4 else 4)
    if kind == 0:
        return rng.choice([None, True, False])
    if kind == 1:
        return rng.randint(-(2**70), 2**70)
    if kind == 2:
        return rng.uniform(-1e300, 1e300)
    if kind == 3:
        return "".join(
            chr(rng.choice([rng.randint(0, 0x7F), rng.randint(0, 0xD7FF)])) for _ in range(8)
        )
    if kind in (4, 5):
        return [_json_value(rng, depth + 1) for _ in range(rng.randint(0, 4))]
    return {str(rng.random()): _json_value(rng, depth + 1) for _ in range(rng.randint(0, 4))}


def test_random_json_values_round_trip(tmp_path: Path) -> None:
    rng = random.Random(SEED + 2)
    for case in range(200):
        value = _json_value(rng)
        write_json_atomic(tmp_path / "v.json", value, indent=rng.choice([None, 0, 2, "\t"]))
        raw = (tmp_path / "v.json").read_bytes()
        assert raw.endswith(b"\n") and b"\r" not in raw.replace(b"\\r", b""), case
        assert json.loads(raw.decode("utf-8")) == value, f"seed={SEED + 2} case={case}"


def _cli(monkeypatch: pytest.MonkeyPatch, args: list[str], data: bytes) -> int:
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(data)))
    return main(args)


def test_cli_json_mode_accepts_exactly_strict_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    rng = random.Random(SEED + 3)
    target = tmp_path / "c.json"
    target.write_bytes(b"{}")
    pieces = [b"{", b"}", b"[", b"]", b'"a"', b":", b",", b"1", b"-", b"e5", b"NaN", b"\xff", b" "]
    for case in range(300):
        data = b"".join(rng.choice(pieces) for _ in range(rng.randint(0, 8)))
        before = target.read_bytes()
        try:
            json.loads(data.decode("utf-8"), parse_constant=lambda _: 1 / 0)
            valid = True
        except (ValueError, ZeroDivisionError):
            valid = False
        status = _cli(monkeypatch, ["--json", str(target)], data)
        assert status == (0 if valid else 1), f"seed={SEED + 3} case={case} {data!r}"
        assert target.read_bytes() == (data if valid else before)
        assert len(capsys.readouterr().err) < 300


@pytest.mark.slow
def test_write_time_grows_linearly_with_size(tmp_path: Path) -> None:
    def seconds(size: int) -> float:
        chunk = b"x" * 65536
        start = time.perf_counter()
        with atomic_write(tmp_path / "big", "wb", fsync="none") as f:
            for _ in range(size // len(chunk)):
                f.write(chunk)
        return time.perf_counter() - start

    small = min(seconds(4 << 20) for _ in range(3))
    large = min(seconds(32 << 20) for _ in range(3))
    assert large < 8 * small * 3 + 0.5


@pytest.mark.slow
def test_cleanup_time_grows_linearly_with_the_directory(tmp_path: Path) -> None:
    def seconds(count: int) -> float:
        folder = tmp_path / str(count)
        folder.mkdir()
        for i in range(count):
            (folder / f"file-{i}.txt").write_bytes(b"")
        start = time.perf_counter()
        assert cleanup_temp_files(folder, older_than=0) == []
        return time.perf_counter() - start

    assert seconds(16000) < 4 * seconds(4000) * 3 + 0.5
