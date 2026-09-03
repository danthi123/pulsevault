"""Ingester: Garmin .fit file -> IngestBundle.

Primary target is ACTIVITY files (a recorded workout: session + record + lap),
which always carry absolute timestamps and full GPS/HR tracks — the main FIT
upload use case. MONITOR files (all-day wellness) are supported best-effort:
heart-rate points and stress levels, resolving FIT's 16-bit compressed
timestamps. Body Battery and sleep scores are not in the public FIT profile, so
those still come from the Garmin Connect path.

All FIT-format quirks (semicircle coords, the 1989 epoch, timestamp_16) live in
THIS file — the adapter seam for the FIT path.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone

import fitdecode

from ..models import Source
from .base import IngestBundle, WorkoutData

log = logging.getLogger("pulsevault.fit")

# Seconds between the Unix epoch (1970) and the FIT epoch (1989-12-31 00:00:00 UTC).
FIT_EPOCH = 631065600
_SEMI_TO_DEG = 180.0 / (2**31)


def _to_unix(value) -> int | None:
    """Coerce a FIT timestamp field (datetime or int seconds-since-1989) to unix."""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp())
    try:
        return FIT_EPOCH + int(value)
    except (TypeError, ValueError):
        return None


def _dt(unix: int | None) -> datetime | None:
    return datetime.fromtimestamp(unix, tz=timezone.utc) if unix is not None else None


def _semi(value) -> float | None:
    return value * _SEMI_TO_DEG if isinstance(value, (int, float)) else None


class FitIngester:
    def parse(self, data: bytes, filename: str = "") -> IngestBundle:
        bundle = IngestBundle(source=Source.fit_upload)
        last_unix: int | None = None
        sessions: list[dict] = []
        records: list[dict] = []

        with fitdecode.FitReader(io.BytesIO(data)) as fit:
            for frame in fit:
                if frame.frame_type != fitdecode.FIT_FRAME_DATA:
                    continue
                name = frame.name

                if name == "record":
                    unix = _to_unix(self._g(frame, "timestamp"))
                    if unix is not None:
                        last_unix = unix
                        records.append(self._record(frame, unix))
                elif name == "session":
                    sessions.append(self._session(frame))
                elif name == "stress_level":
                    unix = _to_unix(self._g(frame, "stress_level_time"))
                    val = self._g(frame, "stress_level_value")
                    if unix is not None and val is not None:
                        bundle.stress.append({"ts": _dt(unix), "value": int(val)})
                elif name == "monitoring":
                    last_unix = self._monitoring(frame, bundle, last_unix)

        self._assemble_workouts(bundle, sessions, records, filename)
        return bundle

    # --- helpers ------------------------------------------------------------
    @staticmethod
    def _g(frame, field, fallback=None):
        try:
            return frame.get_value(field, fallback=fallback)
        except KeyError:
            return fallback

    def _record(self, frame, unix: int) -> dict:
        return {
            "ts": _dt(unix),
            "lat": _semi(self._g(frame, "position_lat")),
            "lon": _semi(self._g(frame, "position_long")),
            "hr": self._int(self._g(frame, "heart_rate")),
            "speed": self._g(frame, "enhanced_speed") or self._g(frame, "speed"),
            "cadence": self._g(frame, "cadence"),
            "altitude": self._g(frame, "enhanced_altitude") or self._g(frame, "altitude"),
            "power": self._g(frame, "power"),
            "temperature": self._g(frame, "temperature"),
        }

    def _session(self, frame) -> dict:
        start = _to_unix(self._g(frame, "start_time"))
        elapsed = self._g(frame, "total_elapsed_time") or self._g(frame, "total_timer_time")
        return {
            "start": start,
            "elapsed": elapsed,
            "sport": self._g(frame, "sport"),
            "sub_sport": self._g(frame, "sub_sport"),
            "distance": self._g(frame, "total_distance"),
            "calories": self._int(self._g(frame, "total_calories")),
            "avg_hr": self._int(self._g(frame, "avg_heart_rate")),
            "max_hr": self._int(self._g(frame, "max_heart_rate")),
            "avg_speed": self._g(frame, "enhanced_avg_speed") or self._g(frame, "avg_speed"),
            "ascent": self._g(frame, "total_ascent"),
        }

    def _monitoring(self, frame, bundle, last_unix):
        unix = _to_unix(self._g(frame, "timestamp"))
        if unix is not None:
            last_unix = unix
        else:
            t16 = self._g(frame, "timestamp_16")
            if t16 is not None and last_unix is not None:
                fit_last = last_unix - FIT_EPOCH
                new_fit = fit_last + ((int(t16) - (fit_last & 0xFFFF)) & 0xFFFF)
                unix = FIT_EPOCH + new_fit
        hr = self._int(self._g(frame, "heart_rate"))
        if unix is not None and hr:
            bundle.heart_rate.append({"ts": _dt(unix), "bpm": hr})
        return last_unix

    def _assemble_workouts(self, bundle, sessions, records, filename):
        if not sessions and records:
            # A record-only file: synthesize a single session spanning the track.
            start = min(r["ts"] for r in records)
            sessions = [{"start": int(start.timestamp()), "elapsed": None, "sport": None,
                         "sub_sport": None, "distance": None, "calories": None,
                         "avg_hr": None, "max_hr": None, "avg_speed": None, "ascent": None}]
        for s in sessions:
            if s["start"] is None:
                continue
            start_dt = _dt(s["start"])
            end_dt = _dt(s["start"] + int(s["elapsed"])) if s["elapsed"] else None
            sport = s["sport"]
            atype = str(sport.name if hasattr(sport, "name") else sport) if sport else None
            in_range = [
                r for r in records
                if end_dt is None or (start_dt <= r["ts"] <= end_dt)
            ] if len(sessions) > 1 else records
            bundle.workouts.append(WorkoutData(
                start_ts=start_dt, end_ts=end_dt,
                name=None,  # let the UI title it from activity_type + date (not the filename)
                activity_type=atype, duration_s=s["elapsed"],
                distance_m=s["distance"], calories=s["calories"],
                avg_hr=s["avg_hr"], max_hr=s["max_hr"],
                avg_speed=s["avg_speed"], ascent_m=s["ascent"],
                records=in_range,
            ))

    @staticmethod
    def _int(v):
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None
