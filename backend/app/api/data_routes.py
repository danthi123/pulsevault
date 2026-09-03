"""Read endpoints powering the dashboard and charts."""
from __future__ import annotations

from datetime import date as date_cls
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..auth import require_auth
from ..config import settings
from ..db import get_session

router = APIRouter(prefix="/api", tags=["data"], dependencies=[Depends(require_auth)])

_METRIC_MODELS = {
    "heart_rate": (models.HeartRateSample, "bpm"),
    "steps": (models.StepsSample, "steps"),
    "stress": (models.StressSample, "value"),
    "spo2": (models.Spo2Sample, "value"),
    "body_battery": (models.BodyBatterySample, "level"),
    "respiration": (models.RespirationSample, "value"),
    "hrv": (models.HrvReading, "value_ms"),
}


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.tz)
    except Exception:  # noqa: BLE001
        return ZoneInfo("UTC")


def _parse_day(day: str | None) -> date_cls:
    if day:
        return date_cls.fromisoformat(day)
    return datetime.now(_tz()).date()


def _day_bounds(day: date_cls) -> tuple[datetime, datetime]:
    tz = _tz()
    start = datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)
    end = start + timedelta(days=1)
    return start, end


def _uid(s: Session) -> int:
    u = s.scalar(select(models.User).limit(1))
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user/data yet — run a sync first")
    return u.id


@router.get("/series/{metric}")
def series(metric: str, day: str | None = None, s: Session = Depends(get_session)):
    if metric not in _METRIC_MODELS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown metric {metric}")
    model, value_field = _METRIC_MODELS[metric]
    uid = _uid(s)
    d = _parse_day(day)
    start, end = _day_bounds(d)
    rows = s.scalars(
        select(model).where(model.user_id == uid, model.ts >= start, model.ts < end)
        .order_by(model.ts)
    ).all()
    points = [{"t": r.ts.isoformat(), "v": getattr(r, value_field)} for r in rows]
    return {"metric": metric, "day": d.isoformat(), "points": points}


@router.get("/daily")
def daily(
    start: str | None = None, end: str | None = None, s: Session = Depends(get_session)
):
    uid = _uid(s)
    end_d = _parse_day(end)
    start_d = date_cls.fromisoformat(start) if start else end_d - timedelta(days=29)
    rows = s.scalars(
        select(models.DailySummary)
        .where(
            models.DailySummary.user_id == uid,
            models.DailySummary.day >= start_d,
            models.DailySummary.day <= end_d,
        )
        .order_by(models.DailySummary.day)
    ).all()
    return {"days": [_daily_row(r) for r in rows]}


@router.get("/dashboard")
def dashboard(day: str | None = None, s: Session = Depends(get_session)):
    uid = _uid(s)
    d = _parse_day(day)
    start, end = _day_bounds(d)

    summary = s.scalar(
        select(models.DailySummary).where(
            models.DailySummary.user_id == uid, models.DailySummary.day == d
        )
    )
    # Latest body battery reading of the day.
    bb = s.scalar(
        select(models.BodyBatterySample)
        .where(models.BodyBatterySample.user_id == uid,
               models.BodyBatterySample.ts >= start, models.BodyBatterySample.ts < end)
        .order_by(models.BodyBatterySample.ts.desc()).limit(1)
    )
    # Last night's sleep (session whose wake-day == d).
    sleep = s.scalar(
        select(models.SleepSession).where(
            models.SleepSession.user_id == uid, models.SleepSession.day == d
        )
    )
    return {
        "day": d.isoformat(),
        "summary": _daily_row(summary) if summary else None,
        "body_battery_now": bb.level if bb else None,
        "sleep": _sleep_row(sleep) if sleep else None,
    }


@router.get("/sleep")
def sleep(day: str | None = None, s: Session = Depends(get_session)):
    uid = _uid(s)
    d = _parse_day(day)
    sess = s.scalar(
        select(models.SleepSession).where(
            models.SleepSession.user_id == uid, models.SleepSession.day == d
        )
    )
    if sess is None:
        return {"day": d.isoformat(), "session": None, "stages": []}
    return {
        "day": d.isoformat(),
        "session": _sleep_row(sess),
        "stages": [
            {"start": seg.start_ts.isoformat(), "end": seg.end_ts.isoformat(),
             "stage": seg.stage.value}
            for seg in sorted(sess.stages, key=lambda x: x.start_ts)
        ],
    }


@router.get("/hrv")
def hrv(start: str | None = None, end: str | None = None, s: Session = Depends(get_session)):
    uid = _uid(s)
    end_d = _parse_day(end)
    start_d = date_cls.fromisoformat(start) if start else end_d - timedelta(days=29)
    rows = s.scalars(
        select(models.HrvSummary).where(
            models.HrvSummary.user_id == uid,
            models.HrvSummary.day >= start_d, models.HrvSummary.day <= end_d,
        ).order_by(models.HrvSummary.day)
    ).all()
    return {"days": [
        {"day": r.day.isoformat(), "last_night_avg": r.last_night_avg,
         "baseline_low": r.baseline_low, "baseline_high": r.baseline_high,
         "status": r.status}
        for r in rows
    ]}


@router.get("/workouts")
def workouts(
    limit: int = Query(30, le=200), s: Session = Depends(get_session)
):
    uid = _uid(s)
    rows = s.scalars(
        select(models.Workout).where(models.Workout.user_id == uid)
        .order_by(models.Workout.start_ts.desc()).limit(limit)
    ).all()
    return {"workouts": [_workout_row(w) for w in rows]}


@router.get("/workouts/{workout_id}")
def workout_detail(workout_id: int, s: Session = Depends(get_session)):
    uid = _uid(s)
    w = s.scalar(
        select(models.Workout).where(
            models.Workout.id == workout_id, models.Workout.user_id == uid
        )
    )
    if w is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workout not found")
    recs = sorted(w.records, key=lambda r: r.ts)
    return {
        "workout": _workout_row(w),
        "track": [
            {"lat": r.lat, "lon": r.lon} for r in recs if r.lat is not None and r.lon is not None
        ],
        "records": [
            {"t": r.ts.isoformat(), "hr": r.hr, "speed": r.speed, "altitude": r.altitude,
             "cadence": r.cadence, "power": r.power}
            for r in recs
        ],
    }


# --- serializers ------------------------------------------------------------
def _daily_row(r: models.DailySummary) -> dict:
    return {
        "day": r.day.isoformat(), "steps": r.steps, "steps_goal": r.steps_goal,
        "distance_m": r.distance_m, "active_seconds": r.active_seconds,
        "floors": r.floors, "calories": r.calories, "resting_hr": r.resting_hr,
        "min_hr": r.min_hr, "max_hr": r.max_hr, "avg_stress": r.avg_stress,
        "body_battery_high": r.body_battery_high, "body_battery_low": r.body_battery_low,
        "intensity_minutes": r.intensity_minutes, "vo2max": r.vo2max,
        "training_status": r.training_status,
    }


def _sleep_row(r: models.SleepSession) -> dict:
    return {
        "start": r.start_ts.isoformat(), "end": r.end_ts.isoformat(),
        "deep_s": r.deep_s, "light_s": r.light_s, "rem_s": r.rem_s,
        "awake_s": r.awake_s, "total_s": r.total_s, "score": r.score,
    }


def _workout_row(w: models.Workout) -> dict:
    return {
        "id": w.id, "name": w.name, "activity_type": w.activity_type,
        "source": w.source.value if w.source else None,
        "start": w.start_ts.isoformat(), "end": w.end_ts.isoformat() if w.end_ts else None,
        "duration_s": w.duration_s, "distance_m": w.distance_m, "calories": w.calories,
        "avg_hr": w.avg_hr, "max_hr": w.max_hr, "avg_speed": w.avg_speed,
        "ascent_m": w.ascent_m,
    }
