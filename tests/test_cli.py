"""The command line tool, run as a real subprocess with real pipes."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from conftest import child_env, leftovers

from durablewrite import __version__


def run(*args: str, stdin: bytes = b"") -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "durablewrite", *args],
        input=stdin,
        capture_output=True,
        env=child_env(),
        timeout=60,
    )


def test_stdin_is_written_to_the_target(tmp_path: Path) -> None:
    target = tmp_path / "out.bin"
    result = run(str(target), stdin=b"line 1\r\nline 2\x00\xff")
    assert result.returncode == 0, result.stderr
    assert result.stdout == b""
    assert target.read_bytes() == b"line 1\r\nline 2\x00\xff"
    assert leftovers(tmp_path, target.name) == []


def test_reading_and_writing_the_same_file_in_one_pipeline(tmp_path: Path) -> None:
    target = tmp_path / "names.txt"
    target.write_bytes(b"b\na\nc\n")
    # Like a shell running `durablewrite --append names.txt < names.txt`: only the
    # child keeps the file open, as its standard input.
    with open(target, "rb") as source:
        child = subprocess.Popen(
            [sys.executable, "-m", "durablewrite", "--append", str(target)],
            stdin=source,
            stderr=subprocess.PIPE,
            env=child_env(),
        )
    _, stderr = child.communicate(timeout=60)
    assert child.returncode == 0, stderr
    assert target.read_bytes() == b"b\na\nc\nb\na\nc\n"
    assert leftovers(tmp_path, target.name) == []


def test_append_keeps_the_existing_content(tmp_path: Path) -> None:
    target = tmp_path / "log.txt"
    target.write_bytes(b"one\n")
    assert run("--append", str(target), stdin=b"two\n").returncode == 0
    assert target.read_bytes() == b"one\ntwo\n"


def test_append_creates_a_missing_file(tmp_path: Path) -> None:
    target = tmp_path / "log.txt"
    assert run("-a", str(target), stdin=b"first\n").returncode == 0
    assert target.read_bytes() == b"first\n"


def test_valid_json_is_written(tmp_path: Path) -> None:
    target = tmp_path / "c.json"
    assert run("--json", str(target), stdin=b'{"ok": true}\n').returncode == 0
    assert target.read_bytes() == b'{"ok": true}\n'


def test_invalid_json_is_refused_and_the_target_kept(tmp_path: Path) -> None:
    target = tmp_path / "c.json"
    target.write_bytes(b'{"ok": true}')
    result = run("--json", str(target), stdin=b'{"ok": tru')
    assert result.returncode == 1
    assert b"not valid UTF-8 JSON" in result.stderr
    assert target.read_bytes() == b'{"ok": true}'
    assert leftovers(tmp_path, target.name) == []


def test_no_overwrite_fails_on_an_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "once.txt"
    target.write_bytes(b"keep")
    result = run("--no-overwrite", str(target), stdin=b"new")
    assert result.returncode == 1
    assert result.stderr.startswith(b"durablewrite: error:")
    assert target.read_bytes() == b"keep"


def test_a_missing_directory_is_an_error(tmp_path: Path) -> None:
    result = run(str(tmp_path / "missing" / "f.txt"), stdin=b"x")
    assert result.returncode == 1
    assert b"durablewrite: error:" in result.stderr


def test_bad_arguments_exit_with_status_one(tmp_path: Path) -> None:
    for args in (["--permissions", "9z"], ["--attempts", "0"], ["--json", "--append"], []):
        result = run(*args, str(tmp_path / "f")) if args else run()
        assert result.returncode == 1, args
        assert b"error:" in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_fsync_and_permissions_options_are_accepted(tmp_path: Path) -> None:
    target = tmp_path / "f.txt"
    result = run("--fsync", "none", "--permissions", "644", "--attempts", "2", str(target))
    assert result.returncode == 0, result.stderr
    assert target.read_bytes() == b""


def test_help_shows_runnable_examples() -> None:
    result = run("--help")
    assert result.returncode == 0
    assert b"sort names.txt | durablewrite names.txt" in result.stdout
    assert b"--no-overwrite" in result.stdout


def test_version() -> None:
    result = run("--version")
    assert result.stdout.decode().strip() == f"durablewrite {__version__}"
