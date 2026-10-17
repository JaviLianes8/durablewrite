"""The documentation the guarantees rest on still says what the guide relies on.

The pages are fetched by ``scripts/fetch_oracles.py`` into a local folder that is
never committed; each manifest entry lists the identifiers and terms the guide's
claims depend on. Skipped until the pages are fetched.
"""

from __future__ import annotations

import html
import json
import re

import pytest
from conftest import TESTS_DIR

MANIFEST = json.loads((TESTS_DIR / "oracle" / "MANIFEST.json").read_text(encoding="utf-8"))
PAGES = sorted(name for name, entry in MANIFEST.items() if entry["kind"] == "page")


def test_every_entry_records_its_origin() -> None:
    for name, entry in MANIFEST.items():
        assert entry["url"].startswith("https://"), name
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]), name
        assert entry["size"] > 0 and entry["fetched"] and entry["licence"], name


@pytest.mark.parametrize("name", PAGES)
def test_the_page_still_states_the_facts_we_rely_on(name: str) -> None:
    page = TESTS_DIR / "oracle" / "pages" / f"{name}.html"
    if not page.is_file():
        pytest.skip("pages not fetched (scripts/fetch_oracles.py)")
    raw = page.read_text(encoding="utf-8", errors="replace")
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw)).split())
    for fact in MANIFEST[name]["facts"]:
        assert fact in text, (name, fact)


def test_the_pages_folder_is_not_part_of_the_repository() -> None:
    ignore = (TESTS_DIR.parent / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "tests/oracle/*" in ignore and "!tests/oracle/MANIFEST.json" in ignore
