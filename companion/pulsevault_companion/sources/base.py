"""The contract every sync source implements.

A source knows how to notice the watch and enumerate its FIT files. It stays
dumb — it does NOT parse FIT (the server does). This keeps backends small and
makes porting to a new OS or transport (USB/MTP, folder, BLE) a contained job.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable

# Subfolders on a Garmin device that hold FIT data worth syncing.
GARMIN_FIT_DIRS = ("Activity", "Monitor", "Sleep", "Metrics")


@dataclass
class DeviceFile:
    key: str              # stable unique id (e.g. "Activity/2024-09-01-10-00-00.fit")
    size: int
    read: Callable[[], bytes]


@runtime_checkable
class SyncSource(Protocol):
    name: str

    def available(self) -> bool:
        """True if the watch is currently reachable through this source."""
        ...

    def list_files(self) -> list[DeviceFile]:
        """Enumerate FIT files currently on the device."""
        ...
