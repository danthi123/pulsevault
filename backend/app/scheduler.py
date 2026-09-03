"""Periodic Garmin Connect sync via APScheduler."""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from . import garmin_auth
from .config import settings
from .sync import run_garmin_sync

log = logging.getLogger("pulsevault.scheduler")
_scheduler: BackgroundScheduler | None = None
_did_initial = False


def _tick() -> None:
    global _did_initial
    if not garmin_auth.has_tokens():
        log.info("scheduler: not authenticated yet, skipping")
        return
    # First successful-auth run does a wider backfill; later runs stay light.
    days = settings.initial_backfill_days if not _did_initial else 2
    result = run_garmin_sync(days_back=days, fetch_details=True)
    if result.get("state") == "ok":
        _did_initial = True


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _tick, "interval",
        minutes=max(5, settings.sync_interval_minutes),
        id="garmin_sync", next_run_time=None, coalesce=True, max_instances=1,
    )
    _scheduler.start()
    # Kick an initial attempt shortly after boot (non-blocking).
    _scheduler.add_job(_tick, "date", id="garmin_sync_boot")
    log.info("scheduler started (every %s min)", settings.sync_interval_minutes)


def shutdown() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
