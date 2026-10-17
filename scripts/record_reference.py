"""Record what atomicwrites 1.4.1 does in every scenario of tests/_differential.py.

Needs the reference library fetched by scripts/fetch_oracles.py. Writes
tests/fixtures/atomicwrites-<platform>.json; run it on each platform (Windows,
Linux) with umask 022. The output is program output, not hand-written data.

    python scripts/record_reference.py
"""

from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "tests" / "oracle" / "atomicwrites")]

import _differential  # noqa: E402
import atomicwrites  # noqa: E402


def _open(path: str, mode: str, overwrite: bool) -> object:
    extra = {"encoding": "utf-8"} if mode == "w" else {}
    return atomicwrites.atomic_write(path, mode=mode, overwrite=overwrite, **extra)


def main() -> int:
    if os.name != "nt":
        os.umask(0o022)
    outcomes = {}
    with tempfile.TemporaryDirectory() as scratch:
        for index, name in enumerate(_differential.scenarios()):
            outcome = _differential.run(_open, Path(scratch) / str(index), name)  # type: ignore[arg-type]
            if outcome is not None:
                outcomes[name] = outcome
    name = "windows" if os.name == "nt" else sys.platform
    record = {
        "library": f"atomicwrites {atomicwrites.__version__}",
        "python": platform.python_version(),
        "system": f"{platform.system()} {platform.release()}",
        "outcomes": outcomes,
    }
    out = ROOT / "tests" / "fixtures" / f"atomicwrites-{name}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"{out.name}: {len(outcomes)} scenarios")
    return 0


if __name__ == "__main__":
    sys.exit(main())
