"""Package metadata: version, classifiers, links, no runtime dependencies."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import durablewrite

ROOT = Path(__file__).resolve().parents[1]
tomllib = pytest.importorskip("tomllib")
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def test_version_matches_the_package_and_the_changelog() -> None:
    assert PROJECT["version"] == durablewrite.__version__ == "1.0.0"
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(r"^## \[1\.0\.0\] - \d{4}-\d{2}-\d{2}$", changelog, re.M)


def test_metadata_is_complete_and_stable() -> None:
    classifiers = PROJECT["classifiers"]
    assert "Development Status :: 5 - Production/Stable" in classifiers
    versions = [c.rsplit(" ", 1)[1] for c in classifiers if re.search(r":: 3\.\d+$", c)]
    assert versions == ["3.10", "3.11", "3.12", "3.13", "3.14"]
    assert PROJECT["requires-python"] == ">=3.10"
    assert PROJECT["license"] == "MIT"
    assert PROJECT["dependencies"] == []
    assert "optional-dependencies" not in PROJECT
    assert {"Homepage", "Source", "Issues", "Changelog"} <= set(PROJECT["urls"])
    assert len(PROJECT["keywords"]) >= 5
    assert PROJECT["scripts"] == {"durablewrite": "durablewrite._cli:main"}


def test_source_files_stay_short_and_plain() -> None:
    for path in [*ROOT.joinpath("src").rglob("*.py"), *ROOT.joinpath("tests").glob("*.py")]:
        text = path.read_text(encoding="utf-8")
        assert len(text.splitlines()) <= 200, path.name
        assert chr(0x2014) not in text, path.name
