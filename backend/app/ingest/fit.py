"""Ingester: Garmin .fit file -> IngestBundle.

Primary target is ACTIVITY files (a recorded workout: session + record + lap),
which always carry absolute timestamps and full GPS/HR tracks — the main FIT
upload use case. MONITOR files (all-day wellness) and SLEEP files are supported
best-effort: heart-rate points, steps (differenced from FIT's cumulative
counter), stress levels, SpO2/pulse-ox, respiration, and sleep stages — all
resolving FIT's 16-bit compressed timestamps. Body Battery is not in the public
FIT profile, so it still comes from the Garmin Connect path.

All FIT-format quirks (semicircle coords, the 1989 epoch, timestamp_16) live in
THIS file — the adapter seam for the FIT path.
"""
from __future__ import annotations

import io
import logging
from datetime import datetime, timezone

import fitdecode

from ..models import SleepStage, Source
from .base import IngestBundle, SleepSessionData, SleepStageSeg, WorkoutData

log = logging.getLogger("pulsevault.fit")

# Seconds between the Unix epoch (1970) and the FIT epoch (1989-12-31 00:00:00 UTC).
FIT_EPOCH = 631065600
_SEMI_TO_DEG = 180.0 / (2**31)

# Map the FIT `sleep_level` enum to our SleepStage. The public FIT SDK exposes
# these by name; integer fallbacks below follow the commonly-observed Garmin
# ordering. NOTE: the integer mapping is a best-effort guess and should be
# VERIFIED against a real Garmin SLEEP file — different firmware/SDK versions
# have been seen to number these differently.
_SLEEP_LEVEL_BY_NAME = {
    "awake": SleepStage.awake,
    "light": SleepStage.light,
    "deep": SleepStage.deep,
    "rem": SleepStage.rem,
}
_SLEEP_LEVEL_BY_INT = {
    0: SleepStage.unmeasured,  # often "unmeasured"/no-data
    1: SleepStage.awake,
    2: SleepStage.light,
    3: SleepStage.deep,
    4: SleepStage.rem,
}


def _sleep_stage(value) -> SleepStage | None:
    """Coerce a FIT sleep_level value (enum-ish with .name, str, or int) to SleepStage."""
    if value is None:
        return None
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return _SLEEP_LEVEL_BY_NAME.get(name.lower())
    if isinstance(value, str):
        return _SLEEP_LEVEL_BY_NAME.get(value.lower())
    try:
        return _SLEEP_LEVEL_BY_INT.get(int(value))
    except (TypeError, ValueError):
        return None


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
        file_type: str | None = None
        # Per-day cumulative step counter, for differencing monitoring `steps`.
        step_state: dict = {"day": None, "last": None}
        # Accumulators for a single sleep session assembled from a SLEEP file.
        sleep_segs: list[SleepStageSeg] = []
        sleep_summary: dict = {}

        with fitdecode.FitReader(io.BytesIO(data)) as fit:
            for frame in fit:
                if frame.frame_type != fitdecode.FIT_FRAME_DATA:
                    continue
                name = frame.name

                # Each message type is isolated so one malformed field/record
                # never aborts the whole file.
                try:
                    if name == "file_id":
                        ft = self._g(frame, "type")
                        file_type = str(ft.name if hasattr(ft, "name") else ft) if ft else None
                    elif name == "record":
                        unix = _to_unix(self._g(frame, "timestamp"))
                        if unix is not None:
                            last_unix = unix
                            records.append(self._record(frame, unix))
                    elif name == "session":
                        sessions.append(self._session(frame))
                    elif name == "stress_level":
                        self._stress_level(frame, bundle)
                    elif name == "monitoring":
                        last_unix = self._monitoring(frame, bundle, last_unix, step_state)
                    elif name == "spo2" or name == "pulse_ox":
                        self._spo2(frame, bundle)
                    elif name == "respiration_rate":
                        self._respiration(frame, bundle)
                    elif name == "sleep_level":
                        self._sleep_level(frame, sleep_segs)
                    elif name == "sleep_assessment":
                        self._sleep_assessment(frame, sleep_summary)
                except Exception:  # noqa: BLE001 — best-effort per-message parsing.
                    log.exception("fit: failed to parse %s message in %s", name, filename)

        self._assemble_workouts(bundle, sessions, records, filename)
        self._assemble_sleep(bundle, sleep_segs, sleep_summary)
        log.info("fit: parsed %s (type=%s) -> %s", filename, file_type, bundle.counts())
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

    def _stress_level(self, frame, bundle):
        unix = _to_unix(self._g(frame, "stress_level_time"))
        val = self._g(frame, "stress_level_value")
        if unix is not None and val is not None:
            # Garmin uses negative stress values as sentinels (-1 = no reading,
            # -2 = too much motion). Real stress is 0..100, so drop the sentinels
            # rather than store them — otherwise they show up as bogus chart dips.
            v = int(val)
            if 0 <= v <= 100:
                bundle.stress.append({"ts": _dt(unix), "value": v})

    def _monitoring(self, frame, bundle, last_unix, step_state):
        unix = _to_unix(self._g(frame, "timestamp"))
        if unix is not None:
            last_unix = unix
        else:
            # Compressed 16-bit timestamp: reconstruct against the last full one.
            t16 = self._g(frame, "timestamp_16")
            if t16 is not None and last_unix is not None:
                fit_last = last_unix - FIT_EPOCH
                new_fit = fit_last + ((int(t16) - (fit_last & 0xFFFF)) & 0xFFFF)
                unix = FIT_EPOCH + new_fit
        if unix is None:
            return last_unix
        ts = _dt(unix)

        hr = self._int(self._g(frame, "heart_rate"))
        if hr:
            bundle.heart_rate.append({"ts": ts, "bpm": hr})

        # Steps: monitoring carries a CUMULATIVE per-day step counter. Emit a
        # bucket = delta since the previous monitoring sample on the same day.
        # NOTE: Garmin's exact reset/rollover semantics are uncertain — we treat
        # a decrease (new day boundary / device reset) as a fresh baseline and
        # skip that delta rather than emit a spurious negative/huge bucket.
        steps_cum = self._int(self._g(frame, "steps"))
        if steps_cum is not None:
            day = ts.date()
            if step_state["day"] != day:
                # New day: reset the baseline, emit the day's first cumulative
                # value as its opening bucket.
                step_state["day"] = day
                step_state["last"] = steps_cum
                if steps_cum > 0:
                    bundle.steps.append({"ts": ts, "steps": steps_cum})
            else:
                prev = step_state["last"]
                delta = steps_cum - prev if prev is not None else steps_cum
                if delta < 0:  # counter reset within the day; rebaseline.
                    delta = steps_cum
                step_state["last"] = steps_cum
                if delta > 0:
                    bundle.steps.append({"ts": ts, "steps": delta})

        # Respiration may ride along on monitoring records on some devices.
        resp = self._g(frame, "respiration_rate") or self._g(frame, "respiration")
        rv = self._float(resp)
        if rv is not None and rv > 0:
            bundle.respiration.append({"ts": ts, "value": rv})

        # Pulse-ox can also appear inline on monitoring records.
        spo2 = self._int(self._g(frame, "reading_spo2") or self._g(frame, "spo2"))
        if spo2 and spo2 > 0:
            bundle.spo2.append({"ts": ts, "value": spo2})

        return last_unix

    def _spo2(self, frame, bundle):
        unix = _to_unix(self._g(frame, "timestamp"))
        if unix is None:
            return
        val = self._int(
            self._g(frame, "reading_spo2")
            or self._g(frame, "spo2")
            or self._g(frame, "reading")
        )
        if val and val > 0:  # guard 0/None (device sends 0 for no reading).
            bundle.spo2.append({"ts": _dt(unix), "value": val})

    def _respiration(self, frame, bundle):
        unix = _to_unix(self._g(frame, "timestamp"))
        if unix is None:
            return
        val = self._float(
            self._g(frame, "respiration_rate") or self._g(frame, "value")
        )
        if val is not None and val > 0:  # <=0 encodes "no reading".
            bundle.respiration.append({"ts": _dt(unix), "value": val})

    def _sleep_level(self, frame, sleep_segs):
        unix = _to_unix(self._g(frame, "timestamp"))
        stage = _sleep_stage(self._g(frame, "sleep_level"))
        if unix is None or stage is None:
            return
        ts = _dt(unix)
        # Each sleep_level message marks the START of a stage; the segment runs
        # until the next message (patched up in _assemble_sleep). Store a
        # zero-length placeholder now.
        sleep_segs.append(SleepStageSeg(start_ts=ts, end_ts=ts, stage=stage))

    def _sleep_assessment(self, frame, sleep_summary):
        # Durations are in seconds; field names follow the FIT sleep_assessment
        # message. Any missing field simply stays absent from the summary.
        mapping = {
            "deep_s": ("deep_sleep_duration", "total_deep_sleep_time"),
            "light_s": ("light_sleep_duration", "total_light_sleep_time"),
            "rem_s": ("rem_sleep_duration", "total_rem_sleep_time"),
            "awake_s": ("awake_duration", "total_awake_time"),
            "total_s": ("total_sleep_time", "sleep_duration"),
            "score": ("overall_sleep_score", "sleep_quality_score", "combined_awake_score"),
        }
        for out_key, fields in mapping.items():
            for f in fields:
                v = self._int(self._g(frame, f))
                if v is not None:
                    sleep_summary[out_key] = v
                    break

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

    def _assemble_sleep(self, bundle, sleep_segs, sleep_summary):
        """Assemble ONE SleepSessionData per SLEEP file from stage segments +
        the (optional) sleep_assessment summary."""
        if not sleep_segs and not sleep_summary:
            return

        stages: list[SleepStageSeg] = []
        if sleep_segs:
            ordered = sorted(sleep_segs, key=lambda s: s.start_ts)
            # Close each segment at the next segment's start; the last one gets
            # a nominal 5-min tail (no successor to bound it).
            for i, seg in enumerate(ordered):
                end = ordered[i + 1].start_ts if i + 1 < len(ordered) else seg.start_ts
                if end <= seg.start_ts:
                    end = _dt(int(seg.start_ts.timestamp()) + 300)
                stages.append(SleepStageSeg(seg.start_ts, end, seg.stage))
            start_ts = ordered[0].start_ts
            end_ts = stages[-1].end_ts
        else:
            # Summary-only file: we have no timeline. Skip — a SleepSession
            # requires start/end timestamps we cannot fabricate meaningfully.
            log.info("fit: sleep_assessment present without sleep_level timeline; skipping")
            return

        # Per-stage seconds: prefer the assessment summary; otherwise sum the
        # reconstructed segments.
        per_stage = {SleepStage.deep: 0, SleepStage.light: 0,
                     SleepStage.rem: 0, SleepStage.awake: 0}
        for seg in stages:
            secs = int(seg.end_ts.timestamp() - seg.start_ts.timestamp())
            if seg.stage in per_stage:
                per_stage[seg.stage] += secs

        deep_s = sleep_summary.get("deep_s", per_stage[SleepStage.deep] or None)
        light_s = sleep_summary.get("light_s", per_stage[SleepStage.light] or None)
        rem_s = sleep_summary.get("rem_s", per_stage[SleepStage.rem] or None)
        awake_s = sleep_summary.get("awake_s", per_stage[SleepStage.awake] or None)
        total_s = sleep_summary.get("total_s")
        if total_s is None:
            asleep = sum(v for v in (deep_s, light_s, rem_s) if v)
            total_s = asleep or None

        bundle.sleep.append(SleepSessionData(
            day=end_ts.date(),  # the night's "wake" date
            start_ts=start_ts, end_ts=end_ts,
            deep_s=deep_s, light_s=light_s, rem_s=rem_s, awake_s=awake_s,
            total_s=total_s, score=sleep_summary.get("score"),
            stages=stages,
        ))

    @staticmethod
    def _int(v):
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _float(v):
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None
