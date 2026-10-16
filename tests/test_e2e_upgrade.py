"""Upgrade from the 0.2.0 release on PyPI to the wheel built from this tree.

Needs the network to download 0.2.0; skipped when PyPI cannot be reached.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BIN = "Scripts" if os.name == "nt" else "bin"
PROBE = """
import json, math, os, sys, durablewrite as d
folder = sys.argv[1]
target = os.path.join(folder, "t.txt")
d.write_text_atomic(target, "same")
out = {"version": d.__version__, "content": open(target, encoding="utf-8").read()}
def outcome(call):
    try:
        call()
        return "ok"
    except Exception as exc:
        return type(exc).__name__
out["bytes_path"] = outcome(lambda: d.write_bytes_atomic(os.fsencode(target), b"x"))
out["nan_delay"] = outcome(lambda: d.RetryPolicy(initial_delay=math.nan))
out["nan_age"] = outcome(lambda: d.cleanup_temp_files(folder, older_than=math.nan))
out["names"] = sorted(d.__all__)
print(json.dumps(out))
"""


def _pip(python: Path, *args: str) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "pip", "--python", str(python), "install", "-q", *args]
    return subprocess.run(command, capture_output=True, text=True, timeout=600)


def _probe(python: Path, folder: Path) -> dict[str, object]:
    folder.mkdir()
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    result = subprocess.run(
        [str(python), "-c", PROBE, str(folder)], capture_output=True, text=True, env=env, cwd=folder
    )
    assert result.returncode == 0, result.stderr
    probe: dict[str, object] = json.loads(result.stdout)
    return probe


@pytest.mark.slow
def test_upgrading_from_pypi_keeps_writes_and_tightens_checks(tmp_path: Path) -> None:
    env_dir = tmp_path / "venv"
    venv.create(env_dir, with_pip=False)
    python = env_dir / _BIN / ("python.exe" if os.name == "nt" else "python")
    if _pip(python, "--no-deps", "durablewrite==0.2.0").returncode != 0:
        pytest.skip("PyPI is not reachable")
    before = _probe(python, tmp_path / "before")
    dist = tmp_path / "dist"
    built = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-q", "-w", str(dist), str(_REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert built.returncode == 0, built.stderr
    (wheel,) = dist.glob("durablewrite-*.whl")
    assert _pip(python, "--no-deps", "--no-index", str(wheel)).returncode == 0
    after = _probe(python, tmp_path / "after")
    assert (before["version"], after["version"]) == ("0.2.0", "1.0.0")
    assert before["content"] == after["content"] == "same"
    assert before["names"] == after["names"]
    assert (before["nan_delay"], after["nan_delay"]) == ("ok", "ValueError")
    assert (before["nan_age"], after["nan_age"]) == ("ok", "ValueError")
    assert after["bytes_path"] == "TypeError"
