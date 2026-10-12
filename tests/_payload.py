"""Self-checking payloads: a reader can tell a complete write from a torn one."""

from __future__ import annotations

import hashlib

_HEADER = b"DWPAYLOAD gen=%010d writer=%04d size=%010d sha=%s\n"
_HEADER_LEN = len(_HEADER % (0, 0, 0, b"0" * 64))


def make_payload(generation: int, size: int, writer: int = 0) -> bytes:
    """Return a payload of ``size`` body bytes whose header pins its checksum."""
    unit = b"%d-%d|" % (writer, generation)
    body = (unit * (size // len(unit) + 1))[:size]
    digest = hashlib.sha256(body).hexdigest().encode("ascii")
    return _HEADER % (generation, writer, size, digest) + body


def parse_payload(data: bytes) -> tuple[int, int]:
    """Return ``(generation, writer)`` or raise AssertionError if ``data`` is torn."""
    assert len(data) >= _HEADER_LEN, f"short file: {len(data)} bytes"
    header, body = data[:_HEADER_LEN], data[_HEADER_LEN:]
    fields = dict(part.split(b"=") for part in header.split()[1:])
    assert int(fields[b"size"]) == len(body), "body length does not match the header"
    digest = hashlib.sha256(body).hexdigest().encode("ascii")
    assert fields[b"sha"] == digest, "body checksum does not match the header"
    return int(fields[b"gen"]), int(fields[b"writer"])
