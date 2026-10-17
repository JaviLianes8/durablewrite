"""Fetch the reference material listed in tests/oracle/MANIFEST.json.

None of it is part of the repository. The atomicwrites sdist is checked against
the size and sha256 in the manifest and its package is unpacked to
tests/oracle/atomicwrites/. Documentation pages are saved to tests/oracle/pages/;
they change over time, so a different hash is reported but not refused. The
tests that use this material skip until this script has run.

    python scripts/fetch_oracles.py
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1] / "tests" / "oracle"


def _unpack(body: bytes, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    with tarfile.open(fileobj=io.BytesIO(body), mode="r:gz") as archive:
        for member in archive.getmembers():
            parts = Path(member.name).parts
            if not member.isfile() or len(parts) < 3 or ".." in parts:
                continue
            if parts[1] != "atomicwrites":
                continue
            source = archive.extractfile(member)
            if source is not None:
                path = target.joinpath(*parts[1:])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(source.read())


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "durablewrite-tests"})
    with urllib.request.urlopen(request, timeout=60) as response:
        body: bytes = response.read()
    return body


def main() -> int:
    manifest = json.loads((FOLDER / "MANIFEST.json").read_text(encoding="utf-8"))
    failed = 0
    for name, entry in manifest.items():
        body = _fetch(entry["url"])
        digest = hashlib.sha256(body).hexdigest()
        same = len(body) == entry["size"] and digest == entry["sha256"]
        if entry["kind"] == "package":
            if not same:
                print(f"{name}: got {len(body)} bytes, sha256 {digest}; manifest differs")
                failed += 1
                continue
            _unpack(body, FOLDER / name)
        else:
            pages = FOLDER / "pages"
            pages.mkdir(exist_ok=True)
            (pages / f"{name}.html").write_bytes(body)
        print(f"{name}: {'ok' if same else 'ok (page changed since ' + entry['fetched'] + ')'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
