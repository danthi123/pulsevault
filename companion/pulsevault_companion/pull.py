"""Auto-pull new .fit files off a connected watch into the inbox folder.

Platform-specific: Linux/macOS use the MTP FUSE mount (existing MtpSource);
Windows uses the WPD/PowerShell puller (experimental). Files already pulled are
tracked in state so we never re-copy after the inbox drains + deletes them.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from .state import State

log = logging.getLogger("pulsevault.pull")


def platform_puller():
    if sys.platform.startswith("linux") or sys.platform == "darwin":
        return MtpPuller()
    if sys.platform.startswith("win"):
        from .win_pull import WindowsPuller
        return WindowsPuller()
    return None


class MtpPuller:
    """Copy new GARMIN FIT files off the auto-mounted watch (Linux gvfs / macOS)."""

    name = "mtp"

    def __init__(self):
        from .sources.mtp import MtpSource
        self._src = MtpSource({"type": "mtp"})

    def available(self) -> bool:
        try:
            return self._src.available()
        except Exception:  # noqa: BLE001
            return False

    def copy_new(self, dest: Path, state: State) -> int:
        n = 0
        for f in self._src.list_files():
            if not state.is_new(f.key, f.size):
                continue
            target = dest / Path(f.key).name
            try:
                target.write_bytes(f.read())
            except OSError as exc:
                log.warning("pull failed %s: %s", f.key, exc)
                continue
            state.mark(f.key, f.size)
            n += 1
            log.info("pulled %s", f.key)
        return n
