"""Real end-to-end: build a wheel, install it into a fresh venv, drive the script.

Nothing is mocked. The wheel is built from the working tree, installed without
network access into a throwaway virtual environment, and the installed
``durablewrite`` console script is run as a subprocess with real pipes.
"""

from __future__ import annotations

import os
import subprocess
import sys
import venv
import zipfile
from pathlib import Path

import pytest

from durablewrite import __version__

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BIN = "Scripts" if os.name == "nt" else "bin"


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Return ``(python, script)`` of a venv with the freshly built wheel installed."""
    dist = tmp_path_factory.mktemp("dist")
    built = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-q", "-w", str(dist), str(_REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert built.returncode == 0, built.stderr
    wheels = list(dist.glob("durablewrite-*.whl"))
    assert [w.name for w in wheels] == [f"durablewrite-{__version__}-py3-none-any.whl"]
    with zipfile.ZipFile(wheels[0]) as archive:
        assert "durablewrite/__init__.py" in archive.namelist(), "built from a tree without src"
    env_dir = tmp_path_factory.mktemp("venv")
    # No pip inside the venv: the host pip installs into it with --python, which
    # also works where the interpreter ships without ensurepip.
    venv.create(env_dir, with_pip=False)
    python = env_dir / _BIN / ("python.exe" if os.name == "nt" else "python")
    host_pip = [sys.executable, "-m", "pip", "--python", str(python)]
    subprocess.run(
        [*host_pip, "install", "--no-index", "--no-deps", "-q", str(wheels[0])],
        check=True,
        timeout=300,
    )
    script = env_dir / _BIN / ("durablewrite.exe" if os.name == "nt" else "durablewrite")
    assert script.is_file(), "the wheel did not register the console script"
    return python, script


def _run(
    script: Path, *args: str, stdin: bytes = b"", cwd: Path | None = None
) -> subprocess.CompletedProcess[bytes]:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    return subprocess.run(
        [str(script), *args], input=stdin, capture_output=True, timeout=60, env=env, cwd=cwd
    )


@pytest.mark.slow
def test_installed_script_reports_its_version(installed: tuple[Path, Path]) -> None:
    result = _run(installed[1], "--version")
    assert result.stdout.decode().strip() == f"durablewrite {__version__}"


@pytest.mark.slow
def test_installed_script_writes_stdin_atomically(
    installed: tuple[Path, Path], tmp_path: Path
) -> None:
    target = tmp_path / "data.txt"
    target.write_bytes(b"old\n")
    assert _run(installed[1], str(target), stdin=b"new\n").returncode == 0
    assert _run(installed[1], "--append", str(target), stdin=b"more\n").returncode == 0
    assert target.read_bytes() == b"new\nmore\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data.txt"]


@pytest.mark.slow
def test_installed_script_reports_errors_on_stderr(
    installed: tuple[Path, Path], tmp_path: Path
) -> None:
    target = tmp_path / "c.json"
    target.write_bytes(b"{}")
    result = _run(installed[1], "--json", str(target), stdin=b"{broken")
    assert result.returncode == 1
    assert result.stdout == b""
    assert result.stderr.startswith(b"durablewrite: error:")
    assert target.read_bytes() == b"{}"


@pytest.mark.slow
def test_installed_package_is_the_wheel_not_the_source_tree(
    installed: tuple[Path, Path], tmp_path: Path
) -> None:
    code = "import durablewrite, sys; sys.stdout.write(durablewrite.__file__)"
    result = subprocess.run(
        [str(installed[0]), "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=tmp_path,
        env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
    )
    assert "site-packages" in result.stdout
    assert str(_REPO_ROOT / "src") not in result.stdout
