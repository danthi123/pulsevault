"""Ingester: Garmin Connect cloud -> IngestBundle.

Maps python-garminconnect responses into the normalized model. Every endpoint
is wrapped independently so one failing/absent metric never aborts a sync (the
API is unofficial and payload shapes drift between account types and firmware).

All the Garmin-specific field names and quirks live in THIS file — the
"adapter" seam. If Garmin changes a payload, this is the only place to patch.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .. import models
from ..models import SleepStage, Source
from .base import IngestBundle, SleepSessionData, SleepStageSeg, WorkoutData

log = logging.getLogger("pulsevault.garmin")

# Garmin Connect sleepLevels.activityLevel -> our stage enum.
# Isolated here so it's a one-line fix if it ever needs correcting against data.
_SLEEP_LEVEL = {
    0.0: SleepStage.deep,
    1.0: SleepStage.light,
    2.0: SleepStage.rem,
    3.0: SleepStage.awake,
}


def _from_ms(ms: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _parse_gmt(s: Any) -> datetime | None:
    """Parse Garmin's 'YYYY-MM-DDTHH:MM:SS.0' GMT strings to aware UTC datetimes."""
    if not s:
        return None
    if isinstance(s, (int, float)):
        return _from_ms(s)
    txt = str(s).replace("Z", "").rstrip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(txt, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _num(d: dict, *keys: str) -> Any:
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return None


class GarminConnectIngester:
    def __init__(self, client):
        self.client = client

    def fetch(self, days_back: int, fetch_workout_details: bool = True) -> IngestBundle:
        bundle = IngestBundle(source=Source.garmin_connect)
        today = datetime.now(timezone.utc).date()
        days = [today - timedelta(days=i) for i in range(days_back + 1)]

        for day in days:
            cdate = day.isoformat()
            self._safe(self._daily_summary, bundle, day, cdate)
            self._safe(self._heart_rate, bundle, day, cdate)
            self._safe(self._steps, bundle, day, cdate)
            self._safe(self._stress, bundle, day, cdate)
            self._safe(self._spo2, bundle, day, cdate)
            self._safe(self._respiration, bundle, day, cdate)
            self._safe(self._sleep, bundle, day, cdate)
            self._safe(self._hrv, bundle, day, cdate)
            self._safe(self._max_metrics, bundle, day, cdate)

        self._safe_bb(bundle, days[-1], today)
        self._safe_activities(bundle, days_back, fetch_workout_details)
        return bundle

    # --- per-metric mappers -------------------------------------------------
    def _safe(self, fn, bundle, day, cdate):
        try:
            fn(bundle, day, cdate)
        except Exception as exc:  # noqa: BLE001
            log.warning("garmin %s failed for %s: %s", fn.__name__, cdate, exc)

    def _daily_summary(self, bundle, day, cdate):
        s = self.client.get_user_summary(cdate) or {}
        bundle.daily_summaries.append({
            "day": day,
            "steps": _num(s, "totalSteps"),
            "distance_m": _num(s, "totalDistanceMeters"),
            "active_seconds": _num(s, "activeSeconds", "highlyActiveSeconds"),
            "floors": _num(s, "floorsAscended", "floorsAscendedInMeters"),
            "calories": _num(s, "totalKilocalories", "activeKilocalories"),
            "resting_hr": _num(s, "restingHeartRate"),
            "min_hr": _num(s, "minHeartRate"),
            "max_hr": _num(s, "maxHeartRate"),
            "avg_stress": _num(s, "averageStressLevel"),
            "body_battery_high": _num(s, "bodyBatteryHighestValue"),
            "body_battery_low": _num(s, "bodyBatteryLowestValue"),
            "intensity_minutes": _num(s, "moderateIntensityMinutes"),
            "steps_goal": _num(s, "dailyStepGoal"),
        })

    def _heart_rate(self, bundle, day, cdate):
        hr = self.client.get_heart_rates(cdate) or {}
        for pair in hr.get("heartRateValues") or []:
            if not pair or pair[1] is None:
                continue
            ts = _from_ms(pair[0])
            if ts:
                bundle.heart_rate.append({"ts": ts, "bpm": int(pair[1])})

    def _steps(self, bundle, day, cdate):
        for b in self.client.get_steps_data(cdate) or []:
            ts = _parse_gmt(b.get("startGMT"))
            if ts is None or b.get("steps") is None:
                continue
            bundle.steps.append({
                "ts": ts, "steps": int(b["steps"]),
                "activity_level": b.get("primaryActivityLevel"),
            })

    def _stress(self, bundle, day, cdate):
        st = self.client.get_stress_data(cdate) or {}
        for pair in st.get("stressValuesArray") or []:
            ts = _from_ms(pair[0])
            if ts and pair[1] is not None:
                bundle.stress.append({"ts": ts, "value": int(pair[1])})

    def _spo2(self, bundle, day, cdate):
        sp = self.client.get_spo2_data(cdate) or {}
        # Key/shape drifts by API version: modern is spO2SingleValues /
        # continuousReadingDTOList (list of [ts, value] pairs OR dicts); older
        # was spO2ValuesArray. Pulse-ox is often disabled, so this is frequently
        # empty — that's genuinely "no data", not a bug.
        arr = (sp.get("spO2SingleValues") or sp.get("continuousReadingDTOList")
               or sp.get("spO2ValuesArray") or sp.get("spo2ValuesArray") or [])
        for item in arr:
            if isinstance(item, dict):
                ts = _from_ms(item.get("epochTimestamp") or item.get("timestamp")) \
                    or _parse_gmt(item.get("startGMT"))
                val = item.get("spo2Reading") or item.get("value") or item.get("spo2")
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                ts, val = _from_ms(item[0]), item[1]
            else:
                continue
            if ts and val is not None:
                bundle.spo2.append({"ts": ts, "value": int(val)})

    def _respiration(self, bundle, day, cdate):
        rp = self.client.get_respiration_data(cdate) or {}
        for pair in rp.get("respirationValuesArray") or []:
            ts = _from_ms(pair[0])
            if ts and pair[1] is not None and pair[1] > 0:
                bundle.respiration.append({"ts": ts, "value": float(pair[1])})

    def _sleep(self, bundle, day, cdate):
        data = self.client.get_sleep_data(cdate) or {}
        dto = data.get("dailySleepDTO") or {}
        start = _from_ms(dto.get("sleepStartTimestampGMT")) or _parse_gmt(dto.get("sleepStartTimestampGMT"))
        end = _from_ms(dto.get("sleepEndTimestampGMT")) or _parse_gmt(dto.get("sleepEndTimestampGMT"))
        if not (start and end):
            return
        scores = dto.get("sleepScores") or {}
        overall = (scores.get("overall") or {}).get("value") if isinstance(scores, dict) else None
        seg_list: list[SleepStageSeg] = []
        for lvl in data.get("sleepLevels") or []:
            s_ts = _parse_gmt(lvl.get("startGMT"))
            e_ts = _parse_gmt(lvl.get("endGMT"))
            stage = _SLEEP_LEVEL.get(float(lvl.get("activityLevel", -1)), SleepStage.unmeasured)
            if s_ts and e_ts:
                seg_list.append(SleepStageSeg(s_ts, e_ts, stage))
        bundle.sleep.append(SleepSessionData(
            day=day, start_ts=start, end_ts=end,
            deep_s=dto.get("deepSleepSeconds"), light_s=dto.get("lightSleepSeconds"),
            rem_s=dto.get("remSleepSeconds"), awake_s=dto.get("awakeSleepSeconds"),
            total_s=dto.get("sleepTimeSeconds"), score=overall, stages=seg_list,
        ))
        # Overnight SpO2 sometimes only appears nested in the sleep payload.
        for pt in (data.get("wellnessEpochSPO2DataDTOList") or []):
            ts = _parse_gmt(pt.get("epochTimestamp"))
            val = pt.get("spo2Reading")
            if ts and val is not None:
                bundle.spo2.append({"ts": ts, "value": int(val)})

    def _hrv(self, bundle, day, cdate):
        data = self.client.get_hrv_data(cdate) or {}
        summ = data.get("hrvSummary") or {}
        baseline = summ.get("baseline") or {}
        if summ:
            bundle.hrv_summary.append({
                "day": day,
                "last_night_avg": summ.get("lastNightAvg"),
                "baseline_low": baseline.get("lowUpper") or baseline.get("balancedLow"),
                "baseline_high": baseline.get("balancedUpper") or baseline.get("markerValue"),
                "status": summ.get("status"),
            })
        for r in data.get("hrvReadings") or []:
            ts = _parse_gmt(r.get("readingTimeGMT")) or _from_ms(r.get("readingTimeGMT"))
            if ts and r.get("hrvValue") is not None:
                bundle.hrv.append({"ts": ts, "value_ms": float(r["hrvValue"])})

    def _max_metrics(self, bundle, day, cdate):
        data = self.client.get_max_metrics(cdate) or []
        if not data:
            return
        generic = (data[0] or {}).get("generic") or {}
        vo2 = generic.get("vo2MaxPreciseValue") or generic.get("vo2MaxValue")
        if vo2 is not None and bundle.daily_summaries:
            for ds in bundle.daily_summaries:
                if ds["day"] == day:
                    ds["vo2max"] = vo2
                    break

    # --- multi-day endpoints -----------------------------------------------
    def _safe_bb(self, bundle, start_day: date, end_day: date):
        try:
            data = self.client.get_body_battery(start_day.isoformat(), end_day.isoformat()) or []
            for day_entry in data:
                for pair in day_entry.get("bodyBatteryValuesArray") or []:
                    if not pair or len(pair) < 2:
                        continue
                    ts = _from_ms(pair[0])
                    # Current API: [ts, level]. Older: [ts, status, level].
                    if len(pair) >= 3:
                        level, status = pair[2], pair[1]
                    else:
                        level, status = pair[1], None
                    if ts is None or level is None:
                        continue
                    bundle.body_battery.append({"ts": ts, "level": int(level), "status": status})
        except Exception as exc:  # noqa: BLE001
            log.warning("garmin body_battery failed: %s", exc)

    def _safe_activities(self, bundle, days_back: int, fetch_details: bool):
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_back + 1)
            activities = self.client.get_activities(0, 30) or []
            for a in activities:
                start = _parse_gmt(a.get("startTimeGMT")) or _from_ms(a.get("beginTimestamp"))
                if start is None or start < cutoff:
                    continue
                atype = ((a.get("activityType") or {}).get("typeKey"))
                dur = a.get("duration")
                w = WorkoutData(
                    start_ts=start,
                    external_id=str(a.get("activityId")) if a.get("activityId") else None,
                    name=a.get("activityName"), activity_type=atype,
                    end_ts=start + timedelta(seconds=dur) if dur else None,
                    duration_s=dur, distance_m=a.get("distance"),
                    calories=int(a["calories"]) if a.get("calories") else None,
                    avg_hr=int(a["averageHR"]) if a.get("averageHR") else None,
                    max_hr=int(a["maxHR"]) if a.get("maxHR") else None,
                    avg_speed=a.get("averageSpeed"), ascent_m=a.get("elevationGain"),
                )
                if fetch_details and a.get("activityId"):
                    self._activity_records(w, a["activityId"])
                bundle.workouts.append(w)
        except Exception as exc:  # noqa: BLE001
            log.warning("garmin activities failed: %s", exc)

    def _activity_records(self, w: WorkoutData, activity_id: Any):
        try:
            det = self.client.get_activity_details(activity_id, maxchart=2000, maxpoly=0) or {}
        except TypeError:
            det = self.client.get_activity_details(activity_id) or {}
        except Exception as exc:  # noqa: BLE001
            log.warning("activity details %s failed: %s", activity_id, exc)
            return
        descriptors = det.get("metricDescriptors") or []
        idx = {d.get("key"): d.get("metricsIndex") for d in descriptors}

        def g(metrics, key):
            i = idx.get(key)
            if i is None or i >= len(metrics):
                return None
            return metrics[i]

        for row in det.get("activityDetailMetrics") or []:
            m = row.get("metrics") or []
            ts = _from_ms(g(m, "directTimestamp"))
            if ts is None:
                continue
            w.records.append({
                "ts": ts,
                "lat": g(m, "directLatitude"),
                "lon": g(m, "directLongitude"),
                "hr": int(g(m, "directHeartRate")) if g(m, "directHeartRate") else None,
                "speed": g(m, "directSpeed"),
                "cadence": g(m, "directRunCadence") or g(m, "directBikeCadence"),
                "altitude": g(m, "directElevation"),
                "power": g(m, "directPower"),
                "temperature": g(m, "directAirTemperature"),
            })
