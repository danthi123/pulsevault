"""CRC-16/ARC (poly 0x8005 reflected = 0xA001, init 0x0000) — the checksum used
by GFDI message envelopes and, in seeded form, by file-transfer chunks.

Verify against a real packet capture before trusting byte-for-byte; the standard
check value CRC16-ARC("123456789") == 0xBB3D is asserted in the self-test.
"""
from __future__ import annotations


def crc16(data: bytes, seed: int = 0) -> int:
    crc = seed & 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if (crc & 1) else (crc >> 1)
    return crc & 0xFFFF
