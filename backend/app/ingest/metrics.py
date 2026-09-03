"""Ingester: on-watch Connect IQ app JSON -> IngestBundle.

The watch app reads recent samples from Toybox.SensorHistory / ActivityMonitor
and POSTs them here. This captures the Garmin-proprietary metrics (stress, Body
Battery) that FIT/Apple Health don't reliably expose — cloud-free, straight off
the wrist through the phone/WiFi.

JSON contract (timestamps are UNIX epoch seconds, UTC):
{
  "device": "fenix7",
  "metrics": {
    "heart_rate":   [[epoch, bpm], ...],
    "stress":       [[epoch, level], ...],
    "body_battery": [[epoch, level], ...],
    "spo2":         [[epoch, pct], ...],
    "respiration":  [[epoch, brpm], ...]
  },
  "today": {"date": "YYYY-MM-DD"|null, "steps": int, "calories": int, "distance_m": float}
}
Every field is optional; unknown metrics are ignored.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models import Source
from .base import IngestBundle

# metric name in payload -> (bundle attribute, value key)
_SIMPLE = {
    "heart_rate": ("heart_rate", "bpm"),
    "stress": ("stress", "value"),
    "spo2": ("spo2", "value"),
    "respiration": ("respiration", "value"),
}


def _dt(epoch: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def parse(payload: dict) -> IngestBundle:
    bundle = IngestBundle(source=Source.watch_ciq)
    metrics = payload.get("metrics") or {}

    for name, (attr, vkey) in _SIMPLE.items():
        target = getattr(bundle, attr)
        for pair in metrics.get(name) or []:
            ts = _dt(pair[0]) if pair else None
            if ts is None or len(pair) < 2 or pair[1] is None:
                continue
            val = float(pair[1]) if attr == "respiration" else int(pair[1])
            target.append({"ts": ts, vkey: val})

    for pair in metrics.get("body_battery") or []:
        ts = _dt(pair[0]) if pair else None
        if ts is not None and len(pair) >= 2 and pair[1] is not None:
            bundle.body_battery.append({"ts": ts, "level": int(pair[1])})

    today = payload.get("today") or {}
    if today:
        day = today.get("date")
        d = datetime.fromisoformat(day).date() if day else datetime.now(timezone.utc).date()
        bundle.daily_summaries.append({
            "day": d,
            "steps": today.get("steps"),
            "calories": today.get("calories"),
            "distance_m": today.get("distance_m"),
        })
    return bundle
