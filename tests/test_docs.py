"""Every documented example runs: docstrings, constant docstrings and the README."""

from __future__ import annotations

import ast
import doctest
import importlib
import inspect
import itertools
import os
import re
from pathlib import Path

import pytest
from conftest import TESTS_DIR

import durablewrite

MODULES = sorted(
    f"durablewrite.{p.stem}"
    for p in Path(durablewrite.__file__).parent.glob("_*.py")
    if p.stem != "__main__"
)
README = (TESTS_DIR.parent / "README.md").read_text(encoding="utf-8")


def _attribute_docstrings(module_name: str) -> dict[str, str]:
    """Docstrings written as a string right after a module-level assignment."""
    module = importlib.import_module(module_name)
    source = inspect.getsource(module)
    body = ast.parse(source).body
    found: dict[str, str] = {}
    for node, after in itertools.pairwise(body):
        if (
            isinstance(node, ast.Assign)
            and isinstance(after, ast.Expr)
            and isinstance(after.value, ast.Constant)
            and isinstance(after.value.value, str)
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found[target.id] = after.value.value
    return found


@pytest.mark.parametrize("module_name", MODULES)
def test_module_doctests_pass(
    module_name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    module = importlib.import_module(module_name)
    result = doctest.testmod(module, verbose=False, report=True)
    assert result.failed == 0
    parser, runner = doctest.DocTestParser(), doctest.DocTestRunner()
    for name, text in _attribute_docstrings(module_name).items():
        test = parser.get_doctest(text, dict(vars(module)), name, module_name, 0)
        assert runner.run(test).failed == 0, name


def test_every_public_name_has_a_runnable_example() -> None:
    constants: dict[str, str] = {}
    for module_name in MODULES:
        constants.update(_attribute_docstrings(module_name))
    for name in durablewrite.__all__:
        obj = getattr(durablewrite, name)
        doc = constants.get(name) if name.isupper() or name == "FsyncLevel" else obj.__doc__
        assert doc and ">>>" in doc, name


def test_readme_python_examples_run_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocks = re.findall(r"```python\n(.*?)```", README, re.S)
    assert len(blocks) >= 3
    monkeypatch.chdir(tmp_path)
    namespace: dict[str, object] = {}
    for block in blocks:
        exec(compile(block, "README.md", "exec"), namespace)
    assert (tmp_path / "report.csv").read_text(encoding="utf-8") == "id,name\n1,ada\n2,grace\n"
    assert (tmp_path / "config.json").read_bytes() == b'{\n  "ready": true\n}\n'
    assert (tmp_path / "held.txt").read_text(encoding="utf-8") == "x"
    assert not any(name.endswith(".dwtmp") for name in os.listdir(tmp_path))


def test_readme_links_are_absolute_and_name_the_guide_and_changelog() -> None:
    links = re.findall(r"\]\(([^)]+)\)", README)
    assert all(link.startswith("https://") for link in links), links
    assert any(link.endswith("/GUIDE.md") for link in links)
    assert any(link.endswith("/CHANGELOG.md") for link in links)
    assert chr(0x2014) not in README
