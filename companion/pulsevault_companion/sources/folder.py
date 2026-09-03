"""Folder source: watch a directory tree for .fit files.

OS-agnostic and dependency-free. Covers: older mass-storage Garmins mounted as
a drive, a gvfs/Explorer-mounted MTP path, or a plain "drop FIT files here"
folder you sync with Syncthing/Nextcloud.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .base import DeviceFile

log = logging.getLogger("pulsevault.folder")


class FolderSource:
    def __init__(self, spec: dict[str, Any]):
        self.name = "folder"
        self.root = Path(spec["path"]).expanduser() if spec.get("path") else None
        if self.root is None:
            raise ValueError("folder source requires a 'path'")

    def available(self) -> bool:
        return self.root.is_dir()

    def list_files(self) -> list[DeviceFile]:
        out: list[DeviceFile] = []
        for p in self.root.rglob("*"):
            if p.is_file() and p.suffix.lower() == ".fit":
                try:
                    size = p.stat().st_size
                except OSError:
                    continue
                rel = str(p.relative_to(self.root))
                out.append(DeviceFile(key=rel, size=size, read=_reader(p)))
        return out


def _reader(path: Path):
    def _read() -> bytes:
        return path.read_bytes()
    return _read
