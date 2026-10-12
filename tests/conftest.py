from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
SRC_DIR = TESTS_DIR.parent / "src"
WORKER = TESTS_DIR / "_worker.py"


def child_env() -> dict[str, str]:
    """Environment for child processes that import the package from ``src``."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(SRC_DIR), env.get("PYTHONPATH")]))
    return env


def spawn_worker(*args: str) -> subprocess.Popen[str]:
    """Start ``_worker.py`` with ``args`` and a readable stdout pipe."""
    return subprocess.Popen(
        [sys.executable, str(WORKER), *args],
        stdout=subprocess.PIPE,
        text=True,
        env=child_env(),
    )


def leftovers(directory: Path, keep: str) -> list[str]:
    """Names in ``directory`` other than ``keep``."""
    return sorted(p.name for p in directory.iterdir() if p.name != keep)


def can_symlink(tmp_path: Path) -> bool:
    probe = tmp_path / "symlink-probe"
    try:
        probe.symlink_to(tmp_path / "missing")
    except (OSError, NotImplementedError):
        return False
    probe.unlink()
    return True


def is_root() -> bool:
    """True when running as uid 0 on POSIX, where permission checks are bypassed."""
    geteuid = getattr(os, "geteuid", None)
    return geteuid is not None and geteuid() == 0


posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX behaviour")
windows_only = pytest.mark.skipif(os.name != "nt", reason="Windows behaviour")
