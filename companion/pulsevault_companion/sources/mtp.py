"""MTP source: auto-detect a Garmin watch exposed as an MTP FUSE mount.

The Fenix 7 (like most modern Garmin wearables) speaks MTP, not USB mass
storage. On a Linux desktop it is auto-mounted by gvfs under
``/run/user/<uid>/gvfs/mtp:host=.../`` when you plug it in; we discover that
mount, locate the ``GARMIN`` folder, and read FIT files straight off it.

Portability:
- Linux (gvfs/GNOME/most DEs): works out of the box via the default globs.
- macOS / other: point ``mount_globs`` at your MTP FUSE mount root.
- Windows: MTP is a COM (WPD) API, not a path — use the ``folder`` source after
  copying in Explorer, or a future WPD backend. (Design seam is here.)

If your DE does NOT auto-mount (e.g. a headless box), mount once with
``jmtpfs``/``go-mtpfs`` and set that path as ``mount_globs``.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .base import GARMIN_FIT_DIRS, DeviceFile

log = logging.getLogger("pulsevault.mtp")


def _default_globs() -> list[str]:
    uid = getattr(os, "getuid", lambda: None)()
    globs = []
    if uid is not None:
        globs.append(f"/run/user/{uid}/gvfs/*")
    globs.append("/run/user/*/gvfs/*")  # fallback across uids
    return globs


class MtpSource:
    def __init__(self, spec: dict[str, Any]):
        self.name = "mtp"
        self.mount_globs: list[str] = spec.get("mount_globs") or _default_globs()
        # How deep under a mount root to hunt for the GARMIN dir.
        self.max_depth: int = int(spec.get("max_depth", 4))

    # --- discovery ----------------------------------------------------------
    def _candidate_mounts(self) -> list[Path]:
        found: list[Path] = []
        for g in self.mount_globs:
            base = Path(g)
            # Expand a trailing glob manually to avoid importing glob semantics.
            parent, pattern = base.parent, base.name
            if not parent.exists():
                continue
            try:
                for child in parent.glob(pattern):
                    if child.is_dir():
                        found.append(child)
            except OSError:
                continue
        return found

    def _find_garmin_root(self) -> Path | None:
        for mount in self._candidate_mounts():
            garmin = _find_dir(mount, "garmin", self.max_depth)
            if garmin is not None:
                return garmin
        return None

    def available(self) -> bool:
        return self._find_garmin_root() is not None

    def list_files(self) -> list[DeviceFile]:
        root = self._find_garmin_root()
        if root is None:
            return []
        out: list[DeviceFile] = []
        for sub in GARMIN_FIT_DIRS:
            d = _child_ci(root, sub)
            if d is None:
                continue
            for p in sorted(d.iterdir()):
                if p.is_file() and p.suffix.lower() == ".fit":
                    try:
                        size = p.stat().st_size
                    except OSError:
                        continue
                    out.append(DeviceFile(key=f"{sub}/{p.name}", size=size, read=_reader(p)))
        return out


def _child_ci(parent: Path, name: str) -> Path | None:
    """Case-insensitive single-level child lookup."""
    try:
        for c in parent.iterdir():
            if c.name.lower() == name.lower() and c.is_dir():
                return c
    except OSError:
        return None
    return None


def _find_dir(root: Path, name: str, max_depth: int) -> Path | None:
    """Breadth-first hunt for a directory named `name` (case-insensitive)."""
    frontier = [(root, 0)]
    while frontier:
        cur, depth = frontier.pop(0)
        try:
            children = list(cur.iterdir())
        except OSError:
            continue
        for c in children:
            if not c.is_dir():
                continue
            if c.name.lower() == name.lower():
                return c
            if depth < max_depth:
                frontier.append((c, depth + 1))
    return None


def _reader(path: Path):
    def _read() -> bytes:
        return path.read_bytes()
    return _read
