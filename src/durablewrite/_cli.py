"""``durablewrite`` command: write standard input to a file atomically, like sponge."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
from typing import IO, NoReturn

from . import __version__
from ._atomic import atomic_write
from ._errors import DirectorySyncError
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

The target is replaced only once standard input reaches end of file, so a
pipeline may read the same file it writes (sort f | durablewrite f). On POSIX
`durablewrite f < f` works too; on Windows the shell keeps a redirected file
open, which blocks the rename, so that form is refused: pipe the file instead.
Concurrent --append runs may lose each other's lines.

exit status: 0 on success; 1 on any error, with the target left as it was;
130 when interrupted;
3 when the target was replaced but its directory could not be fsynced.
"""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {_cut(message)}\n")


def _cut(message: str) -> str:
    """Keep a message to 120 characters, keeping its end where the file name is."""
    return message if len(message) <= 120 else message[:58] + "..." + message[-59:]


def _short(text: str) -> str:
    return repr(text if len(text) <= 40 else text[:37] + "...")


def _octal(text: str) -> int:
    try:
        value = int(text, 8)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an octal mode: {_short(text)}") from None
    if not 0 <= value <= 0o7777:
        raise argparse.ArgumentTypeError(f"mode out of range: {_short(text)}")
    return value


def _positive(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        value = 0
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer: {_short(text)}")
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


def _reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not valid JSON")


def _check_json(payload: bytes) -> None:
    try:
        # Numbers are only checked, not converted: int() refuses over 4300 digits.
        text = payload.decode("utf-8")
        json.loads(text, parse_constant=_reject_constant, parse_int=len, parse_float=len)
    except (ValueError, RecursionError) as exc:
        raise ValueError(f"standard input is not valid UTF-8 JSON ({exc})") from exc


def _refuse_redirected_target(source: IO[bytes], target: str) -> None:
    """On Windows, fail fast when standard input is the target file itself."""
    if os.name != "nt":
        return
    try:
        src, dst = os.fstat(source.fileno()), os.stat(target)
    except (OSError, ValueError):
        return
    if stat.S_ISREG(src.st_mode) and os.path.samestat(src, dst):
        raise ValueError(
            "TARGET is also standard input and Windows keeps it open. "
            "Pipe it instead: type FILE | durablewrite FILE"
        )


def _write(args: argparse.Namespace, source: IO[bytes]) -> None:
    _refuse_redirected_target(source, args.target)
    payload: bytes | None = None
    if args.json:
        payload = source.read()
        _check_json(payload)
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


def main(argv: list[str] | None = None) -> int:
    """Run the command line tool and return its exit status."""
    args = build_parser().parse_args(argv)
    if sys.stdin is None:
        print("durablewrite: error: standard input is closed", file=sys.stderr)
        return 1
    try:
        _write(args, sys.stdin.buffer)
    except DirectorySyncError as exc:
        print(f"durablewrite: warning: {_cut(f'{args.target}: {exc}')}", file=sys.stderr)
        return 3
    except (OSError, ValueError) as exc:
        print(f"durablewrite: error: {_cut(str(exc))}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("durablewrite: interrupted, target left unchanged", file=sys.stderr)
        return 130
    return 0
