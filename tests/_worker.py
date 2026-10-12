"""Child process used by the crash and concurrency tests. Run as a script.

python _worker.py loop TARGET SIZE        write generations forever
python _worker.py writes TARGET WRITER N  write N generations, then exit
python _worker.py hold TARGET SECONDS     keep TARGET open for SECONDS
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _payload import make_payload

from durablewrite import atomic_write, write_bytes_atomic

_CHUNK = 16 * 1024


def _loop(target: str, size: int) -> None:
    print("started", flush=True)
    generation = 1
    while True:
        payload = make_payload(generation, size + generation % 7 * 4096)
        with atomic_write(target, "wb", fsync="file" if generation % 2 else "none") as f:
            for start in range(0, len(payload), _CHUNK):
                f.write(payload[start : start + _CHUNK])
        generation += 1


def _writes(target: str, writer: int, count: int) -> None:
    for generation in range(1, count + 1):
        write_bytes_atomic(target, make_payload(generation, 64 * 1024, writer), fsync="none")
    print("done", flush=True)


def _hold(target: str, seconds: float) -> None:
    with open(target, "rb"):
        print("holding", flush=True)
        time.sleep(seconds)


if __name__ == "__main__":
    command, path, *rest = sys.argv[1:]
    if command == "loop":
        _loop(path, int(rest[0]))
    elif command == "writes":
        _writes(path, int(rest[0]), int(rest[1]))
    elif command == "hold":
        _hold(path, float(rest[0]))
    else:
        raise SystemExit(f"unknown command {command!r}")
