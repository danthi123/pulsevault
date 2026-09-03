"""COBS framing as used by Garmin's Multi-Link channel: a standard COBS-encoded
payload wrapped in a leading and trailing 0x00 delimiter, so frames are
self-delimiting on the notify characteristic.

encode_frame/decode_frame handle one whole frame. FrameReassembler accumulates
raw notification bytes and yields complete decoded GFDI payloads as delimiters
arrive (a single GFDI message can span several BLE notifications).
"""
from __future__ import annotations

from typing import Iterator

DELIM = 0x00


def cobs_encode(data: bytes) -> bytes:
    out = bytearray()
    code_idx = 0
    out.append(0)  # placeholder for the first code byte
    code = 1
    for b in data:
        if b != 0:
            out.append(b)
            code += 1
            if code == 0xFF:
                out[code_idx] = code
                code_idx = len(out)
                out.append(0)
                code = 1
        else:
            out[code_idx] = code
            code_idx = len(out)
            out.append(0)
            code = 1
    out[code_idx] = code
    return bytes(out)


def cobs_decode(enc: bytes) -> bytes:
    out = bytearray()
    i, n = 0, len(enc)
    while i < n:
        code = enc[i]
        i += 1
        if code == 0:
            raise ValueError("invalid COBS code byte 0x00")
        for _ in range(code - 1):
            if i < n:
                out.append(enc[i])
                i += 1
        if code != 0xFF and i < n:
            out.append(0)
    return bytes(out)


def encode_frame(payload: bytes) -> bytes:
    return bytes([DELIM]) + cobs_encode(payload) + bytes([DELIM])


def decode_frame(frame: bytes) -> bytes:
    body = frame
    if body and body[0] == DELIM:
        body = body[1:]
    if body and body[-1] == DELIM:
        body = body[:-1]
    return cobs_decode(body)


class FrameReassembler:
    """Feed raw notification bytes; get back decoded payloads."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, chunk: bytes) -> Iterator[bytes]:
        for b in chunk:
            if b == DELIM:
                if self._buf:
                    try:
                        yield cobs_decode(bytes(self._buf))
                    except ValueError:
                        pass  # malformed frame — resync on next delimiter
                    self._buf.clear()
                # a leading delimiter with empty buffer just starts a frame
            else:
                self._buf.append(b)
