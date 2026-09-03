"""Multi-Link (ML) layer: GATT UUIDs, the per-packet handle byte, and the
handle-management control frames used to register/close GFDI services.

BLE GATT (V2 communicator, used by Fenix 7):
  ML service : 6A4E2800-667B-11E3-949A-0800200C9A66
  notify char: 6A4E2810-...   (from watch)
  write char : 6A4E2820-...   (to watch)  == notify UUID + 0x10

Packet on the characteristic = [handle:1] + <COBS frame bytes>.
  handle 0x00      -> handle-management control message
  handle == GFDI   -> COBS-encoded GFDI payload for that service
"""
from __future__ import annotations

import struct
from enum import IntEnum

_BASE = "6A4E{:04X}-667B-11E3-949A-0800200C9A66"
ML_SERVICE_UUID = _BASE.format(0x2800).lower()
NOTIFY_UUID = _BASE.format(0x2810).lower()
WRITE_UUID = _BASE.format(0x2820).lower()

GADGETBRIDGE_CLIENT_ID = 2  # client id used in registration frames
CONTROL_HANDLE = 0x00
MLR_FLAG_MASK = 0x80  # high bit of byte0 marks a Multi-Link-reliable packet


class RequestType(IntEnum):
    REGISTER_ML_REQ = 0
    REGISTER_ML_RESP = 1
    CLOSE_HANDLE_REQ = 2
    CLOSE_HANDLE_RESP = 3
    UNK_HANDLE = 4
    CLOSE_ALL_REQ = 5
    CLOSE_ALL_RESP = 6


class Service(IntEnum):
    GFDI = 1
    REGISTRATION = 4
    REALTIME_HR = 6
    REALTIME_STEPS = 7
    REALTIME_CALORIES = 8
    REALTIME_INTENSITY = 10
    REALTIME_HRV = 12
    REALTIME_STRESS = 13
    REALTIME_SPO2 = 19
    REALTIME_BODY_BATTERY = 20
    REALTIME_RESPIRATION = 21


def register_service(service: int, reliable: bool, client_id: int = GADGETBRIDGE_CLIENT_ID) -> bytes:
    """Handle-management REGISTER_ML_REQ frame (13 bytes)."""
    return (
        bytes([CONTROL_HANDLE, RequestType.REGISTER_ML_REQ])
        + struct.pack("<Q", client_id)
        + struct.pack("<H", service)
        + bytes([2 if reliable else 0])
    )


def close_all(client_id: int = GADGETBRIDGE_CLIENT_ID) -> bytes:
    """Handle-management CLOSE_ALL_REQ frame."""
    return (
        bytes([CONTROL_HANDLE, RequestType.CLOSE_ALL_REQ])
        + struct.pack("<Q", client_id)
        + struct.pack("<H", 0x0000)
    )


def parse_register_response(payload: bytes) -> dict:
    """Parse a REGISTER_ML_RESP body: [serviceCode:2][status:1][handle:1][reliable:1]."""
    if len(payload) < 5:
        raise ValueError("register response too short")
    service, status, handle, reliable = struct.unpack_from("<HBBB", payload, 0)
    return {"service": service, "status": status, "handle": handle, "reliable": bool(reliable)}


def frame_gfdi(handle: int, cobs_frame: bytes) -> bytes:
    """Prefix a COBS-encoded GFDI frame with its ML handle byte (no fragmentation)."""
    return bytes([handle & 0xFF]) + cobs_frame


def is_mlr(packet: bytes) -> bool:
    return bool(packet) and (packet[0] & MLR_FLAG_MASK) != 0
