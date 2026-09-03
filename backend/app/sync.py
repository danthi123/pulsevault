"""Sync orchestration: Garmin Connect pull + FIT upload -> persist."""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from . import garmin_auth
from .db import SessionLocal
from .ingest import metrics as metrics_ingest
from .ingest.base import persist
from .ingest.fit import FitIngester
from .ingest.garmin_connect import GarminConnectIngester
from .models import User

log = logging.getLogger("pulsevault.sync")

_sync_lock = threading.Lock()
# Last-run status surfaced to the UI.
last_status: dict[str, Any] = {"state": "idle", "at": None, "detail": None}


def get_or_create_user() -> int:
    with SessionLocal() as s:
        user = s.scalar(select(User).limit(1))
        if user is None:
            user = User(name="me")
            s.add(user)
            s.commit()
        return user.id


def run_garmin_sync(days_back: int, fetch_details: bool = True) -> dict[str, Any]:
    """Pull `days_back` days from Garmin Connect and persist. Idempotent."""
    if not _sync_lock.acquire(blocking=False):
        return {"state": "busy"}
    try:
        last_status.update(state="running", at=_now(), detail=f"garmin {days_back}d")
        if not garmin_auth.has_tokens():
            last_status.update(state="error", at=_now(), detail="not authenticated")
            return {"state": "error", "reason": "not_authenticated"}
        client = garmin_auth.get_client()
        user_id = get_or_create_user()
        bundle = GarminConnectIngester(client).fetch(days_back, fetch_details)
        with SessionLocal() as s:
            stats = persist(s, user_id, bundle)
        last_status.update(state="ok", at=_now(), detail=stats)
        log.info("garmin sync ok: %s", stats)
        return {"state": "ok", "stats": stats}
    except Exception as exc:  # noqa: BLE001
        log.exception("garmin sync failed")
        last_status.update(state="error", at=_now(), detail=str(exc))
        return {"state": "error", "reason": str(exc)}
    finally:
        _sync_lock.release()


def ingest_fit(data: bytes, filename: str) -> dict[str, Any]:
    user_id = get_or_create_user()
    bundle = FitIngester().parse(data, filename=filename)
    with SessionLocal() as s:
        stats = persist(s, user_id, bundle)
    log.info("fit ingest %s: %s", filename, stats)
    return {"state": "ok", "file": filename, "stats": stats}


def ingest_metrics(payload: dict) -> dict[str, Any]:
    """Persist a live-metrics push from the on-watch Connect IQ app."""
    user_id = get_or_create_user()
    bundle = metrics_ingest.parse(payload)
    with SessionLocal() as s:
        stats = persist(s, user_id, bundle)
    log.info("metrics ingest: %s", stats)
    return {"state": "ok", "stats": stats}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
