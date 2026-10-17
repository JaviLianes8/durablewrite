"""durablewrite against the reference library, atomicwrites 1.4.1.

``tests/fixtures/atomicwrites-<platform>.json`` is what atomicwrites did in each
scenario of ``_differential.py`` (recorded by ``scripts/record_reference.py``).
Writing a plain file, new or replaced, must look the same from outside. The
other scenarios are the documented differences: durablewrite refuses a
directory and an existing name before the block runs, and writes through a
symlink instead of replacing it. When the library is fetched, the recording is
also rerun live.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import IO, Any

import _differential
import pytest
from conftest import TESTS_DIR

from durablewrite import atomic_write

PLATFORM = "windows" if os.name == "nt" else sys.platform
FIXTURE = TESTS_DIR / "fixtures" / f"atomicwrites-{PLATFORM}.json"
RECORDED: dict[str, Any] = (
    json.loads(FIXTURE.read_text(encoding="utf-8"))["outcomes"] if FIXTURE.is_file() else {}
)
pytestmark = pytest.mark.skipif(not RECORDED, reason=f"no recording for {PLATFORM}")


def _durable(path: str, mode: str, overwrite: bool) -> Any:
    return atomic_write(path, mode, overwrite=overwrite, encoding="utf-8" if mode == "w" else None)


def _refused(name: str) -> bool:
    state, _, overwrite, _, _ = name.split("-")
    return state == "directory" or (overwrite == "exclusive" and state in ("file", "symlink"))


def _same_outside(name: str) -> bool:
    state, _, _, _, ending = name.split("-")
    return not _refused(name) and (state in ("absent", "file") or ending == "raise")


def _content_view(outcome: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in outcome.items() if k != "mode"}


@pytest.mark.parametrize("name", sorted(RECORDED))
def test_each_scenario_matches_or_differs_as_documented(tmp_path: Path, name: str) -> None:
    ours = _differential.run(_durable, tmp_path / "s", name)
    if ours is None:
        pytest.skip("symlinks are not available to this account")
    theirs = RECORDED[name]
    assert ours["leftovers"] == 0
    if _same_outside(name):
        assert _content_view(ours) == _content_view(theirs)
        return
    assert ours != theirs
    if _refused(name):
        assert not ours["ran"], "refused before the block runs"
        assert ours["error"] in ("IsADirectoryError", "FileExistsError")
    else:  # a symlink or dangling link is written through and kept
        assert ours["kind"] == "symlink"


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
@pytest.mark.parametrize("name", sorted(n for n in RECORDED if n.startswith("absent-")))
def test_new_files_follow_the_umask_where_atomicwrites_makes_them_private(
    tmp_path: Path, name: str
) -> None:
    old = os.umask(0o022)
    try:
        ours = _differential.run(_durable, tmp_path / "s", name)
    finally:
        os.umask(old)
    assert ours is not None
    if name.endswith("-ok"):
        assert RECORDED[name]["mode"] == 0o600
        assert ours["mode"] == 0o644


def test_the_recording_reruns_live(tmp_path: Path) -> None:
    oracle = TESTS_DIR / "oracle" / "atomicwrites"
    if not (oracle / "atomicwrites" / "__init__.py").is_file():
        pytest.skip("reference library not fetched (scripts/fetch_oracles.py)")
    sys.path.insert(0, str(oracle))
    try:
        atomicwrites = importlib.import_module("atomicwrites")
    finally:
        sys.path.remove(str(oracle))

    def theirs(path: str, mode: str, overwrite: bool) -> IO[Any]:
        extra = {"encoding": "utf-8"} if mode == "w" else {}
        opened: IO[Any] = atomicwrites.atomic_write(path, mode=mode, overwrite=overwrite, **extra)
        return opened

    old = os.umask(0o022)
    try:
        for index, name in enumerate(sorted(RECORDED)):
            assert _differential.run(theirs, tmp_path / str(index), name) == RECORDED[name], name
    finally:
        os.umask(old)
