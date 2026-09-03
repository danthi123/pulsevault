"""Tracks which device files have already been uploaded, so re-scans are cheap
and we never re-send the same FIT file. (The server dedupes too — this is just
to avoid pointless uploads.)"""
from __future__ import annotations

import json
from pathlib import Path


class State:
    def __init__(self, path: Path):
        self.path = path
        self._seen: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        try:
            self._seen = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            self._seen = {}

    def is_new(self, key: str, size: int) -> bool:
        return self._seen.get(key) != size

    def keys(self):
        return list(self._seen.keys())

    def mark(self, key: str, size: int) -> None:
        self._seen[key] = size
        self._save()

    def _save(self) -> None:
        try:
            self.path.write_text(json.dumps(self._seen))
        except OSError:
            pass
