"""Scenarios run through durablewrite and through the reference library, atomicwrites.

Each scenario prepares a folder, writes through one library's context manager
and records what an outside observer sees: the exception raised (by class name),
whether the block ran, the target's final content and what else is left behind.
"""

from __future__ import annotations

import itertools
import os
import shutil
import stat
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import IO, Any

Opener = Callable[[str, str, bool], AbstractContextManager[IO[Any]]]

STATES = ("absent", "file", "directory", "symlink", "dangling")
PAYLOADS = {"empty": "", "ascii": "line one\nline two\n", "unicode": "café ☃\r\n"}


def scenarios() -> list[str]:
    """Names like ``file-wb-overwrite-ascii-ok``; the grid is hand-chosen."""
    grid = itertools.product(
        STATES, ("w", "wb"), ("overwrite", "exclusive"), PAYLOADS, ("ok", "raise")
    )
    return ["-".join(parts) for parts in grid]


def _prepare(folder: Path, state: str) -> bool:
    folder.mkdir()
    target = folder / "target"
    if state in ("file", "symlink"):
        (folder / "real" if state == "symlink" else target).write_bytes(b"OLD")
    if state == "directory":
        target.mkdir()
    if state in ("symlink", "dangling"):
        try:
            target.symlink_to(folder / "real")
        except OSError:  # no symlink privilege on this Windows account
            shutil.rmtree(folder)
            return False
    return True


def _snapshot(folder: Path) -> dict[str, Any]:
    target = folder / "target"
    if target.is_symlink():
        kind = "symlink"
    elif target.is_dir():
        kind = "directory"
    else:
        kind = "file" if target.exists() else "missing"
    content = target.read_bytes().decode("utf-8") if target.is_file() else None
    others = sorted(p.name for p in folder.iterdir() if p.name not in ("target", "real"))
    real = folder / "real"
    mode = stat.S_IMODE(target.stat().st_mode) if kind == "file" and os.name != "nt" else None
    return {
        "kind": kind,
        "mode": mode,
        "content": content,
        "real": real.read_bytes().decode("utf-8") if real.is_file() else None,
        "leftovers": len(others),
    }


def run(opener: Opener, folder: Path, name: str) -> dict[str, Any] | None:
    """Run scenario ``name`` in the new ``folder``; None if it cannot run here."""
    state, mode, overwrite, payload, ending = name.split("-")
    if not _prepare(folder, state):
        return None
    text = PAYLOADS[payload]
    ran = False
    error = None
    try:
        with opener(os.fspath(folder / "target"), mode, overwrite == "overwrite") as f:
            ran = True
            f.write(text if mode == "w" else text.encode("utf-8"))
            if ending == "raise":
                raise RuntimeError("stop")
    except Exception as exc:  # the class name is what is compared
        error = type(exc).__name__
    return {"error": error, "ran": ran, **_snapshot(folder)}
