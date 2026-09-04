"""Ingester: a Garmin Connect account data export (the "Export Your Data" zip)
-> IngestBundle.

The export is a zip of JSON files — sleep sessions and daily wellness summaries —
and, for some accounts, activity `.fit` files. Intraday time-series (per-minute
HR/stress/etc.) are generally NOT in the export; those come from the live token
pull. So this focuses on SLEEP (with stages) + DAILY SUMMARIES and hands any
`.fit` inside to the existing FIT ingester.

Garmin's export layout drifts between account types, so the ingester also returns
a STRUCTURE REPORT (files seen, detected type, record counts, and the keys of any
unrecognised JSON) — an unknown layout shows up in the response instead of being
silently skipped, which is exactly what we need to finish the mappings against a
real export.
"""
from __future__ import annotations

import io
import json
import logging
import zipfile
from datetime import date

from ..models import SleepStage, Source
from .base import IngestBundle, SleepSessionData, SleepStageSeg
from .fit import FitIngester
from .garmin_connect import _SLEEP_LEVEL, _from_ms, _num, _parse_gmt

log = logging.getLogger("pulsevault.garmin_export")

_MERGE_ATTRS = ("daily_summaries", "heart_rate", "steps", "stress", "spo2",
                "body_battery", "respiration", "hrv", "hrv_summary", "sleep", "workouts")


def _as_date(v) -> date | None:
    if isinstance(v, str) and len(v) >= 10:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
    return None


class GarminExportIngester:
    def parse(self, data: bytes) -> tuple[IngestBundle, dict]:
        bundle = IngestBundle(source=Source.garmin_connect)
        report: dict = {"files": [], "fit_files": 0, "sleep_nights": 0,
                        "daily_summaries": 0, "unrecognized": []}
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            self._ingest_json(bundle, "upload.json", data, report)  # maybe a bare JSON
            return bundle, report

        for name in zf.namelist():
            if name.endswith("/"):
                continue
            low = name.lower()
            try:
                raw = zf.read(name)
            except Exception:  # noqa: BLE001
                continue
            if low.endswith(".fit"):
                self._ingest_fit(bundle, name, raw, report)
            elif low.endswith(".zip"):
                # Activities ship as .fit inside a nested zip (UploadedFiles_*.zip).
                try:
                    inner = zipfile.ZipFile(io.BytesIO(raw))
                    for iname in inner.namelist():
                        if iname.lower().endswith(".fit"):
                            self._ingest_fit(bundle, iname, inner.read(iname), report)
                except (zipfile.BadZipFile, RuntimeError):
                    pass  # encrypted/other zips (e.g. ECG) — skip
            elif low.endswith(".json"):
                self._ingest_json(bundle, name, raw, report)
        return bundle, report

    def _ingest_fit(self, bundle, name, raw, report):
        try:
            fb = FitIngester().parse(raw, name.rsplit("/", 1)[-1])
            # sleepData.json is the authoritative sleep source (has scores); FIT
            # sleep files would create duplicate nights under a different start_ts.
            fb.sleep = []
            self._merge(bundle, fb)
            report["fit_files"] += 1
        except Exception as exc:  # noqa: BLE001
            report["unrecognized"].append({"file": name, "error": str(exc)[:120]})

    # ---- JSON dispatch ----

    def _ingest_json(self, bundle, name, raw, report):
        try:
            obj = json.loads(raw)
        except Exception:  # noqa: BLE001
            return
        records = obj if isinstance(obj, list) else [obj]
        sample = next((r for r in records if isinstance(r, dict)), None)
        if sample is None:
            return
        keys = set(sample.keys())
        low = name.lower()

        if "sleep" in low or ("dailySleepDTO" in keys) or \
                ({"sleepStartTimestampGMT", "sleepEndTimestampGMT"} & keys):
            n = sum(1 for r in records if isinstance(r, dict) and self._sleep(bundle, r))
            report["sleep_nights"] += n
            report["files"].append({"file": name, "type": "sleep", "records": n})
        elif "uds" in low or ({"calendarDate"} & keys and
                              {"totalSteps", "restingHeartRate", "totalKilocalories",
                               "totalDistanceMeters"} & keys):
            n = sum(1 for r in records if isinstance(r, dict) and self._daily(bundle, r))
            report["daily_summaries"] += n
            report["files"].append({"file": name, "type": "daily", "records": n})
        else:
            # Unknown shape — surface it so a mapper can be added.
            report["unrecognized"].append({
                "file": name,
                "record_count": len(records),
                "sample_keys": sorted(keys)[:40],
            })

    # ---- mappers (mirror garmin_connect, tolerant of the flat export shape) ----

    def _sleep(self, bundle, r) -> bool:
        dto = r.get("dailySleepDTO") if isinstance(r.get("dailySleepDTO"), dict) else r
        start = _from_ms(dto.get("sleepStartTimestampGMT")) or _parse_gmt(dto.get("sleepStartTimestampGMT"))
        end = _from_ms(dto.get("sleepEndTimestampGMT")) or _parse_gmt(dto.get("sleepEndTimestampGMT"))
        if not (start and end):
            return False
        day = _as_date(dto.get("calendarDate")) or start.date()
        # Export uses sleepScores.overallScore (a bare int); the live API nests it
        # as .overall.value — support both.
        scores = dto.get("sleepScores") or {}
        score = None
        if isinstance(scores, dict):
            score = scores.get("overallScore")
            if score is None and isinstance(scores.get("overall"), dict):
                score = scores["overall"].get("value")
        if score is None:
            score = _num(dto, "overallSleepScore", "sleepScore")
        # The export carries no sleepLevels hypnogram (the live pull does), just
        # the aggregate seconds — so stages stay empty here.
        segs: list[SleepStageSeg] = []
        for lvl in (r.get("sleepLevels") or dto.get("sleepLevels") or []):
            s_ts = _parse_gmt(lvl.get("startGMT")) or _from_ms(lvl.get("startGMT"))
            e_ts = _parse_gmt(lvl.get("endGMT")) or _from_ms(lvl.get("endGMT"))
            try:
                stage = _SLEEP_LEVEL.get(float(lvl.get("activityLevel", -1)), SleepStage.unmeasured)
            except (TypeError, ValueError):
                stage = SleepStage.unmeasured
            if s_ts and e_ts:
                segs.append(SleepStageSeg(s_ts, e_ts, stage))
        deep, light, rem = (_num(dto, "deepSleepSeconds"), _num(dto, "lightSleepSeconds"),
                            _num(dto, "remSleepSeconds"))
        total = _num(dto, "sleepTimeSeconds")
        if total is None and any(v is not None for v in (deep, light, rem)):
            total = (deep or 0) + (light or 0) + (rem or 0)  # asleep time (excl. awake)
        bundle.sleep.append(SleepSessionData(
            day=day, start_ts=start, end_ts=end,
            deep_s=deep, light_s=light, rem_s=rem, awake_s=_num(dto, "awakeSleepSeconds"),
            total_s=total, score=score, stages=segs,
        ))
        return True

    def _daily(self, bundle, r) -> bool:
        day = _as_date(r.get("calendarDate"))
        if day is None:
            return False
        bundle.daily_summaries.append({
            "day": day,
            "steps": _num(r, "totalSteps"),
            "distance_m": _num(r, "totalDistanceMeters"),
            "active_seconds": _num(r, "activeSeconds", "highlyActiveSeconds"),
            "floors": _num(r, "floorsAscended", "floorsAscendedInMeters"),
            "calories": _num(r, "totalKilocalories", "activeKilocalories"),
            "resting_hr": _num(r, "restingHeartRate"),
            "min_hr": _num(r, "minHeartRate"),
            "max_hr": _num(r, "maxHeartRate"),
            "avg_stress": _num(r, "averageStressLevel"),
            "body_battery_high": _num(r, "bodyBatteryHighestValue"),
            "body_battery_low": _num(r, "bodyBatteryLowestValue"),
            "intensity_minutes": _num(r, "moderateIntensityMinutes"),
            "steps_goal": _num(r, "dailyStepGoal"),
        })
        return True

    def _merge(self, bundle, other):
        for attr in _MERGE_ATTRS:
            getattr(bundle, attr).extend(getattr(other, attr))
