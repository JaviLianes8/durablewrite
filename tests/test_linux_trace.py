"""Linux ground truth at the system call level, through an LD_PRELOAD tracer.

``trace/dwtrace.c`` logs the real libc calls a writer makes and can kill it with
SIGKILL right before or after any of them. The tests check the order the
fsync(2) and rename(2) manual pages ask for (data fsync, rename, directory
fsync), that a kill at every call boundary leaves the old or the new file, and,
when the reference library is fetched, that atomicwrites makes the same calls.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import TESTS_DIR, child_env

from durablewrite import cleanup_temp_files

pytestmark = pytest.mark.skipif(
    not sys.platform.startswith("linux") or shutil.which("gcc") is None,
    reason="needs Linux and gcc",
)

OLD = b"old content"
EXPECTED = {
    "replace": [
        "open temp excl",
        "write temp",
        "fsync temp",
        "rename temp t",
        "open . dir",
        "fsync .",
    ],
    "replace-file": ["open temp excl", "write temp", "fsync temp", "rename temp t"],
    "replace-none": ["open temp excl", "write temp", "rename temp t"],
    "create": [
        "open temp excl",
        "write temp",
        "fsync temp",
        "rename temp t",
        "open . dir",
        "fsync .",
    ],
    "exclusive": [
        "open temp excl",
        "write temp",
        "fsync temp",
        "link temp t",
        "unlink temp",
        "open . dir",
        "fsync .",
    ],
}
WRITER = (
    "import sys; sys.path.insert(0, sys.argv[1]); from _crashpoint import NEW, SCENARIOS;"
    "from durablewrite import atomic_write\n"
    "with atomic_write(sys.argv[3], 'wb', **SCENARIOS[sys.argv[2]]) as f:\n"
    "    for i in range(0, len(NEW), 8192): f.write(NEW[i:i + 8192])\n"
)


@pytest.fixture(scope="module")
def tracer(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("tracer") / "dwtrace.so"
    source = TESTS_DIR / "trace" / "dwtrace.c"
    subprocess.run(
        ["gcc", "-shared", "-fPIC", "-O1", "-o", str(out), str(source), "-ldl"], check=True
    )
    return out


def _normal(line: str) -> str:
    return " ".join("temp" if word.endswith(".dwtmp") else word for word in line.split())


def _trace(tracer: Path, folder: Path, code: list[str], **kill: int) -> tuple[int, list[str]]:
    log = folder.parent / f"{folder.name}.log"
    env = child_env()
    env.update(LD_PRELOAD=str(tracer), DWTRACE_DIR=str(folder), DWTRACE_OUT=str(log))
    env.update({f"DWTRACE_KILL_{k.upper()}": str(v) for k, v in kill.items()})
    child = subprocess.run([sys.executable, "-c", *code], env=env, timeout=120)
    raw = log.read_text().splitlines() if log.exists() else []
    return child.returncode, [_normal(line) for line in raw]


def _collapse(events: list[str]) -> list[str]:
    return [e for i, e in enumerate(events) if i == 0 or e != events[i - 1]]


def _write(tracer: Path, folder: Path, scenario: str, **kill: int) -> tuple[int, list[str]]:
    folder.mkdir()
    if scenario.startswith("replace"):
        (folder / "t").write_bytes(OLD)
    code = [WRITER, str(TESTS_DIR), scenario, str(folder / "t")]
    return _trace(tracer, folder, code, **kill)


@pytest.mark.parametrize("scenario", sorted(EXPECTED))
def test_the_real_system_calls_come_in_the_documented_order(
    tracer: Path, tmp_path: Path, scenario: str
) -> None:
    code, events = _write(tracer, tmp_path / "run", scenario)
    assert code == 0
    assert _collapse(events) == EXPECTED[scenario]


@pytest.mark.slow
@pytest.mark.parametrize("scenario", sorted(EXPECTED))
def test_sigkill_at_every_system_call_leaves_the_old_or_the_new_file(
    tracer: Path, tmp_path: Path, scenario: str
) -> None:
    from _crashpoint import NEW

    _, calls = _write(tracer, tmp_path / "probe", scenario)
    published = next(i for i, c in enumerate(calls, 1) if c.split()[0] in ("rename", "link"))
    for k in range(1, len(calls) + 1):
        for when in ("before", "after"):
            folder = tmp_path / f"{when}{k}"
            code, events = _write(tracer, folder, scenario, **{when: k})
            context = f"{scenario}: SIGKILL {when} call {k} ({calls[k - 1]})"
            assert code == -9, context
            assert events == calls[: k if when == "after" else k - 1], context
            target = folder / "t"
            if k > published or (k == published and when == "after"):
                assert target.read_bytes() == NEW, context
            elif scenario.startswith("replace"):
                assert target.read_bytes() == OLD, context
            else:
                assert not target.exists(), context
            temps = [p for p in os.listdir(folder) if p != "t"]
            assert len(cleanup_temp_files(folder, older_than=0)) == len(temps), context


def test_atomicwrites_makes_the_same_calls(tracer: Path, tmp_path: Path) -> None:
    oracle = TESTS_DIR / "oracle" / "atomicwrites"
    if not (oracle / "atomicwrites" / "__init__.py").is_file():
        pytest.skip("reference library not fetched (scripts/fetch_oracles.py)")
    folder = tmp_path / "aw"
    folder.mkdir()
    (folder / "t").write_bytes(OLD)
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]); from atomicwrites import atomic_write\n"
        "with atomic_write(sys.argv[2], mode='wb', overwrite=True, dir=sys.argv[3]) as f:\n"
        "    f.write(b'new')\n"
    )
    status, events = _trace(tracer, folder, [code, str(oracle), str(folder / "t"), str(folder)])
    assert status == 0
    assert _essential(events) == _essential(EXPECTED["replace"])


def _essential(events: list[str]) -> list[str]:
    """The durability steps: data fsync, rename, directory fsync, in order."""
    keep = [e.split() for e in events if e.split()[0] in ("fsync", "rename")]
    return [" ".join(["temp" if w.startswith("tmp") else w for w in e]) for e in keep]
