"""``durablewrite`` command: write standard input to a file atomically, like sponge."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from contextlib import suppress
from typing import IO, NoReturn

from . import __version__
from ._atomic import atomic_write
from ._options import RetryPolicy

_EPILOG = """\
examples:
  sort names.txt | durablewrite names.txt
      sort a file in place; names.txt is replaced only after sort finishes
  jq '.debug = true' config.json | durablewrite --json config.json
      edit JSON in place; invalid output never replaces the file
  echo "one more line" | durablewrite --append notes.txt
      append atomically: readers see the old file or the longer one
  printf 's3cret' | durablewrite --permissions 600 --no-overwrite token.txt
      create a private file, failing if it already exists

The target is replaced only once standard input reaches end of file, so it is
safe to read from and write to the same file in one pipeline. On any error the
target is left as it was and the exit status is 1.
"""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def _octal(text: str) -> int:
    try:
        value = int(text, 8)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an octal mode: {text!r}") from None
    if not 0 <= value <= 0o7777:
        raise argparse.ArgumentTypeError(f"mode out of range: {text!r}")
    return value


def _positive(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        value = 0
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer: {text!r}")
    return value


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the ``durablewrite`` command."""
    parser = _Parser(
        prog="durablewrite",
        description="Read standard input and write it to TARGET atomically and durably.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("target", metavar="TARGET", help="file to create or replace")
    parser.add_argument("--version", action="version", version=f"durablewrite {__version__}")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "-a", "--append", action="store_true", help="keep the current content and add stdin"
    )
    mode.add_argument(
        "--json", action="store_true", help="refuse to write unless stdin is valid UTF-8 JSON"
    )
    parser.add_argument(
        "--fsync",
        choices=("none", "file", "full"),
        default="full",
        help="what to flush to disk before returning (default: full)",
    )
    parser.add_argument("--no-overwrite", action="store_true", help="fail if TARGET already exists")
    parser.add_argument(
        "--permissions", type=_octal, metavar="OCTAL", help="permission bits, e.g. 644"
    )
    parser.add_argument(
        "--no-follow-symlinks",
        action="store_true",
        help="replace a symlink TARGET itself instead of the file it points to",
    )
    parser.add_argument(
        "--attempts",
        type=_positive,
        default=8,
        metavar="N",
        help="rename attempts while Windows reports TARGET locked (default: 8)",
    )
    return parser


def _write(args: argparse.Namespace, source: IO[bytes]) -> None:
    payload: bytes | None = None
    if args.json:
        payload = source.read()
        try:
            json.loads(payload.decode("utf-8"))
        except ValueError as exc:
            raise ValueError(f"standard input is not valid UTF-8 JSON ({exc})") from exc
    with atomic_write(
        args.target,
        "wb",
        fsync=args.fsync,
        overwrite=not args.no_overwrite,
        permissions=args.permissions,
        follow_symlinks=not args.no_follow_symlinks,
        retry=RetryPolicy(max_attempts=args.attempts),
    ) as out:
        if args.append:
            try:
                with open(args.target, "rb") as current:
                    shutil.copyfileobj(current, out)
            except FileNotFoundError:
                pass
        if payload is not None:
            out.write(payload)
        else:
            shutil.copyfileobj(source, out)
        _release(source)


def _release(source: IO[bytes]) -> None:
    """Close our handle on standard input once it is drained.

    With ``durablewrite f < f`` this process itself holds ``f`` open, and on
    Windows an open handle without ``FILE_SHARE_DELETE`` blocks the rename.
    """
    with suppress(OSError, ValueError):
        os.close(source.fileno())


def main(argv: list[str] | None = None) -> int:
    """Run the command line tool and return its exit status."""
    args = build_parser().parse_args(argv)
    try:
        _write(args, sys.stdin.buffer)
    except (OSError, ValueError) as exc:
        print(f"durablewrite: error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("durablewrite: interrupted, target left unchanged", file=sys.stderr)
        return 130
    return 0
