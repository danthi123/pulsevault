"""GFDI message envelope (inside the COBS frame).

Wire layout (little-endian):
  [length:2]  total length incl. these 2 bytes, the 2 type bytes, payload, and CRC
  [type:2]    see the 0x8000 encoding note below
  [payload...]
  [crc:2]     CRC-16/ARC over bytes [0 .. length-2]

Type encoding: 5000-series message IDs travel with the high bit set —
  wire_type = 0x8000 | (seq << 8) | ((id - 5000) & 0xFF)
On decode, if (type & 0x8000): id = (type & 0xFF) + 5000; seq = (type >> 8) & 0x7F.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum

from .crc import crc16


class Msg(IntEnum):
    RESPONSE = 5000
    DOWNLOAD_REQUEST = 5002
    UPLOAD_REQUEST = 5003
    FILE_TRANSFER_DATA = 5004
    CREATE_FILE = 5005
    DIRECTORY_FILTER = 5007
    SET_FILE_FLAGS = 5008
    FILE_AVAILABLE = 5009
    FIT_DEFINITION = 5011
    FIT_DATA = 5012
    DEVICE_INFORMATION = 5024
    DEVICE_SETTINGS = 5026
    SYSTEM_EVENT = 5030
    SUPPORTED_FILE_TYPES_REQUEST = 5031
    SYNCHRONIZATION = 5037
    CONFIGURATION = 5050
    CURRENT_TIME_REQUEST = 5052
    AUTH_NEGOTIATION = 5101


class Status(IntEnum):
    ACK = 0
    NAK = 1
    UNSUPPORTED = 2
    DECODE_ERROR = 3
    CRC_ERROR = 4
    LENGTH_ERROR = 5


@dataclass
class GfdiMessage:
    msg_id: int
    payload: bytes
    seq: int = 0


def encode(msg_id: int, payload: bytes = b"", seq: int = 0) -> bytes:
    if msg_id >= 5000:
        wire_type = 0x8000 | ((seq & 0x7F) << 8) | ((msg_id - 5000) & 0xFF)
    else:
        wire_type = msg_id & 0xFFFF
    body = struct.pack("<H", wire_type) + payload
    length = 2 + len(body) + 2  # length field + body + crc
    buf = struct.pack("<H", length) + body
    return buf + struct.pack("<H", crc16(buf))


def decode(buf: bytes) -> GfdiMessage:
    if len(buf) < 6:
        raise ValueError("GFDI message too short")
    (length,) = struct.unpack_from("<H", buf, 0)
    if length != len(buf):
        raise ValueError(f"GFDI length mismatch: header {length} != actual {len(buf)}")
    (crc_got,) = struct.unpack_from("<H", buf, length - 2)
    crc_calc = crc16(buf[: length - 2])
    if crc_got != crc_calc:
        raise ValueError(f"GFDI CRC mismatch: {crc_got:#06x} != {crc_calc:#06x}")
    (wire_type,) = struct.unpack_from("<H", buf, 2)
    if wire_type & 0x8000:
        msg_id = (wire_type & 0xFF) + 5000
        seq = (wire_type >> 8) & 0x7F
    else:
        msg_id, seq = wire_type, 0
    return GfdiMessage(msg_id=msg_id, payload=buf[4 : length - 2], seq=seq)
