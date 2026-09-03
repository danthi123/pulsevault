"""Drain the inbox folder: upload each .fit, delete it on success.

A file is deleted only when the server actually accepted+parsed it (accepted>=1).
If the server rejected it (unparseable) the file is kept and logged; if the
upload itself fails (connectivity/server down) we stop and retry next cycle.
Uploads are idempotent server-side, so a re-run never duplicates data.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .uploader import Uploader

log = logging.getLogger("pulsevault.inbox")


def fit_files(fit_dir: Path) -> list[Path]:
    return sorted(p for p in fit_dir.iterdir() if p.is_file() and p.suffix.lower() == ".fit")


def drain(fit_dir: Path, uploader: Uploader) -> int:
    uploaded = 0
    for p in fit_files(fit_dir):
        try:
            data = p.read_bytes()
        except OSError as exc:
            log.warning("cannot read %s: %s", p.name, exc)
            continue
        if not data:
            continue
        try:
            summary = uploader.upload([(p.name, data)])
        except Exception as exc:  # noqa: BLE001 — connectivity/server error: retry later
            log.error("upload failed for %s: %s (kept in inbox, will retry)", p.name, exc)
            break
        if summary.get("accepted", 0):
            try:
                p.unlink()
            except OSError:
                pass
            uploaded += 1
            log.info("uploaded + removed %s", p.name)
        else:
            log.warning("server did not accept %s (kept in inbox): %s", p.name, summary.get("results"))
    return uploaded
