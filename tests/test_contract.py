"""The complete public promise of durablewrite, pinned in one place."""

from __future__ import annotations

import importlib.resources
import os
import pickle
from pathlib import Path

import pytest
from conftest import leftovers

import durablewrite
from durablewrite import (
    DirectorySyncError,
    DurableWriteError,
    SharingViolationError,
    atomic_write,
    write_bytes_atomic,
    write_json_atomic,
    write_text_atomic,
)

# The public API. This list is the contract: the test below fails if the module
# and this list disagree.
PUBLIC_API: list[str] = [
    "DEFAULT_RETRY",
    "NO_RETRY",
    "DirectorySyncError",
    "DurableWriteError",
    "FsyncLevel",
    "RetryPolicy",
    "SharingViolationError",
    "atomic_write",
    "cleanup_temp_files",
    "write_bytes_atomic",
    "write_json_atomic",
    "write_text_atomic",
]


def test_all_lists_exactly_the_public_api() -> None:
    assert sorted(durablewrite.__all__) == sorted(PUBLIC_API)


def test_every_exported_name_resolves() -> None:
    for name in durablewrite.__all__:
        assert hasattr(durablewrite, name)


def test_version_is_a_three_part_string() -> None:
    parts = durablewrite.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_the_package_ships_type_information() -> None:
    assert importlib.resources.files("durablewrite").joinpath("py.typed").is_file()


def test_errors_fit_the_standard_hierarchy() -> None:
    error = SharingViolationError(13, "locked", "f")
    assert isinstance(error, DurableWriteError)
    assert isinstance(error, PermissionError)
    assert isinstance(error, OSError)
    assert issubclass(DurableWriteError, OSError)
    assert issubclass(DirectorySyncError, DurableWriteError)
    assert pickle.loads(pickle.dumps(error)).filename == "f"


@pytest.mark.parametrize("writer", ["text", "bytes", "json", "stream"])
def test_every_writer_replaces_completely_and_leaves_no_temp(tmp_path: Path, writer: str) -> None:
    target = tmp_path / "t"
    target.write_bytes(b"old content that is longer than the new one")
    if writer == "text":
        write_text_atomic(target, "new", newline="")
    elif writer == "bytes":
        write_bytes_atomic(target, b"new")
    elif writer == "json":
        write_json_atomic(target, "new", indent=None)
    else:
        with atomic_write(target, "wb") as f:
            f.write(b"ne")
            f.write(b"w")
    expected = b'"new"\n' if writer == "json" else b"new"
    assert target.read_bytes() == expected
    assert leftovers(tmp_path, "t") == []


@pytest.mark.parametrize("error", [RuntimeError, KeyboardInterrupt])
def test_any_failure_inside_the_block_keeps_the_old_file(
    tmp_path: Path, error: type[BaseException]
) -> None:
    target = tmp_path / "t"
    target.write_bytes(b"old")
    with pytest.raises(error), atomic_write(target, "wb") as f:
        f.write(b"half")
        raise error()
    assert target.read_bytes() == b"old"
    assert leftovers(tmp_path, "t") == []


def test_target_is_untouched_until_the_block_exits(tmp_path: Path) -> None:
    target = tmp_path / "t"
    target.write_bytes(b"old")
    with atomic_write(target, "wb") as f:
        f.write(b"new" * 1000)
        f.flush()
        assert target.read_bytes() == b"old"
    assert target.read_bytes() == b"new" * 1000


def test_writes_accept_str_and_pathlike_paths(tmp_path: Path) -> None:
    write_text_atomic(os.fspath(tmp_path / "a"), "x")
    write_text_atomic(tmp_path / "b", "x")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a", "b"]
