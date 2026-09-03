"""Sync source backends. Add a new backend by implementing SyncSource."""
from __future__ import annotations

from typing import Any

from .base import SyncSource


def build_source(spec: dict[str, Any]) -> SyncSource:
    stype = spec.get("type", "mtp")
    if stype == "folder":
        from .folder import FolderSource
        return FolderSource(spec)
    if stype == "mtp":
        from .mtp import MtpSource
        return MtpSource(spec)
    if stype == "ble":
        from .ble import BleSource
        return BleSource(spec)
    raise ValueError(f"unknown source type: {stype}")
