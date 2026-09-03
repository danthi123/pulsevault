"""BLE source (EXPERIMENTAL): sync a Garmin watch over Bluetooth LE via GFDI.

Status: scaffold. Pulling activity/health FIT files over BLE means speaking
Garmin's proprietary GFDI protocol over "Multi-Link reliable" framing, plus a
pairing/auth handshake that impersonates Garmin Connect. That can only be
brought up iteratively against a physical watch.

What works today:
- `probe()` connects (or just scans) and dumps the GATT table — services and
  characteristic UUIDs/properties. Run `pulsevault-companion ble-probe` and share the
  output; it's the first step to wiring up the real GFDI client here.

The main sync loop treats BLE as unavailable until `list_files()` is implemented,
so enabling this source never breaks USB syncing.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import DeviceFile

log = logging.getLogger("pulsevault.ble")

# Filled in from protocol research; kept here as the single place BLE constants live.
GARMIN_NAME_HINTS = ("fenix", "garmin", "epix", "forerunner", "instinct", "venu")


class BleSource:
    def __init__(self, spec: dict[str, Any]):
        self.name = "ble"
        self.address: str | None = spec.get("address")
        self.name_hints = tuple(h.lower() for h in spec.get("name_hints", GARMIN_NAME_HINTS))
        self.enabled = bool(spec.get("enabled", False))

    def available(self) -> bool:
        # GFDI file transfer not implemented yet — keep the sync loop from using it.
        if self.enabled:
            log.info("BLE source is experimental and not yet syncing; run 'ble-probe' to help bring it up.")
        return False

    def list_files(self) -> list[DeviceFile]:
        raise NotImplementedError("BLE GFDI file transfer not implemented yet")

    # --- diagnostics used by `pulsevault-companion ble-probe` ----------------------
    def probe(self) -> dict:
        return asyncio.run(self._probe_async())

    async def _probe_async(self) -> dict:
        try:
            from bleak import BleakClient, BleakScanner
        except ImportError as exc:
            raise SystemExit(
                "bleak not installed. Install BLE extra:  pipx install 'pulsevault-companion[ble]'  "
                "or  pip install bleak"
            ) from exc

        target = None
        log.info("Scanning for a Garmin watch (10s)…")
        devices = await BleakScanner.discover(timeout=10.0)
        for d in devices:
            name = (d.name or "").lower()
            if self.address and d.address.upper() == self.address.upper():
                target = d
                break
            if any(h in name for h in self.name_hints):
                target = d
                break

        found = [{"name": d.name, "address": d.address} for d in devices]
        if target is None:
            log.warning("No Garmin-looking device found. Make sure it's in pairing range and "
                        "not connected to a phone.")
            return {"connected": False, "seen_devices": found}

        log.info("Connecting to %s (%s)…", target.name, target.address)
        result: dict = {"connected": False, "device": {"name": target.name, "address": target.address},
                        "seen_devices": found, "services": []}
        async with BleakClient(target) as client:
            result["connected"] = client.is_connected
            for service in client.services:
                svc = {"uuid": service.uuid, "description": service.description, "characteristics": []}
                for ch in service.characteristics:
                    svc["characteristics"].append({
                        "uuid": ch.uuid,
                        "properties": ch.properties,
                        "description": ch.description,
                    })
                result["services"].append(svc)
        return result
