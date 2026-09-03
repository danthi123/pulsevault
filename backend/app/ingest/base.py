"""The normalized data contract every ingester produces, plus idempotent persist.

An ingester's only job is to turn some source (Garmin Connect JSON, a FIT file,
a future Gadgetbridge SQLite export) into an :class:`IngestBundle`. Persisting is
shared and dialect-aware, using upserts keyed on the natural constraints in
``app.models`` so re-running any sync never creates duplicates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Session

from .. import models
from ..models import Source


@dataclass
class SleepStageSeg:
    start_ts: datetime
    end_ts: datetime
    stage: models.SleepStage


@dataclass
class SleepSessionData:
    day: date
    start_ts: datetime
    end_ts: datetime
    deep_s: int | None = None
    light_s: int | None = None
    rem_s: int | None = None
    awake_s: int | None = None
    total_s: int | None = None
    score: int | None = None
    stages: list[SleepStageSeg] = field(default_factory=list)


@dataclass
class WorkoutData:
    start_ts: datetime
    external_id: str | None = None
    name: str | None = None
    activity_type: str | None = None
    end_ts: datetime | None = None
    duration_s: float | None = None
    distance_m: float | None = None
    calories: int | None = None
    avg_hr: int | None = None
    max_hr: int | None = None
    avg_speed: float | None = None
    ascent_m: float | None = None
    records: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class IngestBundle:
    """Everything an ingester extracted for one sync/upload."""

    source: Source
    daily_summaries: list[dict[str, Any]] = field(default_factory=list)
    heart_rate: list[dict[str, Any]] = field(default_factory=list)  # {ts, bpm}
    steps: list[dict[str, Any]] = field(default_factory=list)  # {ts, steps, activity_level?}
    stress: list[dict[str, Any]] = field(default_factory=list)  # {ts, value}
    spo2: list[dict[str, Any]] = field(default_factory=list)  # {ts, value}
    body_battery: list[dict[str, Any]] = field(default_factory=list)  # {ts, level, status?}
    respiration: list[dict[str, Any]] = field(default_factory=list)  # {ts, value}
    hrv: list[dict[str, Any]] = field(default_factory=list)  # {ts, value_ms}
    hrv_summary: list[dict[str, Any]] = field(default_factory=list)  # {day, ...}
    sleep: list[SleepSessionData] = field(default_factory=list)
    workouts: list[WorkoutData] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "daily_summaries": len(self.daily_summaries),
            "heart_rate": len(self.heart_rate),
            "steps": len(self.steps),
            "stress": len(self.stress),
            "spo2": len(self.spo2),
            "body_battery": len(self.body_battery),
            "respiration": len(self.respiration),
            "hrv": len(self.hrv),
            "sleep": len(self.sleep),
            "workouts": len(self.workouts),
        }


def _insert_stmt(dialect: Dialect):
    """Return the dialect-specific INSERT that supports on_conflict_do_update."""
    if dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert

        return insert
    if dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert

        return insert
    raise RuntimeError(f"Unsupported DB dialect for upsert: {dialect.name}")


def _upsert(session: Session, model, rows: list[dict], conflict_cols: list[str]) -> int:
    if not rows:
        return 0
    insert = _insert_stmt(session.bind.dialect)
    table_cols = {c.name for c in model.__table__.columns}
    update_cols = [c for c in rows[0].keys() if c not in conflict_cols and c in table_cols]
    # Chunk to keep parameter counts sane.
    total = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i : i + 500]
        stmt = insert(model).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=conflict_cols,
            set_={c: getattr(stmt.excluded, c) for c in update_cols},
        )
        session.execute(stmt)
        total += len(chunk)
    return total


def _tag(rows: list[dict], user_id: int, source: Source) -> list[dict]:
    for r in rows:
        r.setdefault("user_id", user_id)
        r.setdefault("source", source)
    return rows


def persist(session: Session, user_id: int, bundle: IngestBundle) -> dict[str, int]:
    """Idempotently write a bundle. Returns per-table row counts touched."""
    src = bundle.source
    stats: dict[str, int] = {}

    stats["daily_summary"] = _upsert(
        session, models.DailySummary, _tag(bundle.daily_summaries, user_id, src),
        ["user_id", "day"],
    )
    stats["heart_rate"] = _upsert(
        session, models.HeartRateSample, _tag(bundle.heart_rate, user_id, src),
        ["user_id", "ts"],
    )
    stats["steps"] = _upsert(
        session, models.StepsSample, _tag(bundle.steps, user_id, src), ["user_id", "ts"]
    )
    stats["stress"] = _upsert(
        session, models.StressSample, _tag(bundle.stress, user_id, src), ["user_id", "ts"]
    )
    stats["spo2"] = _upsert(
        session, models.Spo2Sample, _tag(bundle.spo2, user_id, src), ["user_id", "ts"]
    )
    stats["body_battery"] = _upsert(
        session, models.BodyBatterySample, _tag(bundle.body_battery, user_id, src),
        ["user_id", "ts"],
    )
    stats["respiration"] = _upsert(
        session, models.RespirationSample, _tag(bundle.respiration, user_id, src),
        ["user_id", "ts"],
    )
    stats["hrv"] = _upsert(
        session, models.HrvReading, _tag(bundle.hrv, user_id, src), ["user_id", "ts"]
    )
    stats["hrv_summary"] = _upsert(
        session, models.HrvSummary, _tag(bundle.hrv_summary, user_id, src),
        ["user_id", "day"],
    )

    stats["sleep"] = _persist_sleep(session, user_id, src, bundle.sleep)
    stats["workouts"] = _persist_workouts(session, user_id, src, bundle.workouts)

    session.commit()
    return stats


def _persist_sleep(session, user_id, source, sessions_: list[SleepSessionData]) -> int:
    insert = _insert_stmt(session.bind.dialect)
    n = 0
    for s in sessions_:
        row = {
            "user_id": user_id, "source": source, "day": s.day,
            "start_ts": s.start_ts, "end_ts": s.end_ts, "deep_s": s.deep_s,
            "light_s": s.light_s, "rem_s": s.rem_s, "awake_s": s.awake_s,
            "total_s": s.total_s, "score": s.score,
        }
        stmt = insert(models.SleepSession).values(row)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "start_ts"],
            set_={k: getattr(stmt.excluded, k) for k in row if k not in ("user_id", "start_ts")},
        ).returning(models.SleepSession.id)
        session_id = session.execute(stmt).scalar_one()
        # Replace stage segments wholesale (idempotent).
        session.execute(
            delete(models.SleepStageSegment).where(
                models.SleepStageSegment.session_id == session_id
            )
        )
        if s.stages:
            session.execute(
                models.SleepStageSegment.__table__.insert(),
                [
                    {"session_id": session_id, "start_ts": seg.start_ts,
                     "end_ts": seg.end_ts, "stage": seg.stage}
                    for seg in s.stages
                ],
            )
        n += 1
    return n


def _persist_workouts(session, user_id, source, workouts: list[WorkoutData]) -> int:
    insert = _insert_stmt(session.bind.dialect)
    n = 0
    for w in workouts:
        row = {
            "user_id": user_id, "source": source, "external_id": w.external_id,
            "name": w.name, "activity_type": w.activity_type, "start_ts": w.start_ts,
            "end_ts": w.end_ts, "duration_s": w.duration_s, "distance_m": w.distance_m,
            "calories": w.calories, "avg_hr": w.avg_hr, "max_hr": w.max_hr,
            "avg_speed": w.avg_speed, "ascent_m": w.ascent_m,
        }
        stmt = insert(models.Workout).values(row)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "start_ts"],
            set_={k: getattr(stmt.excluded, k) for k in row if k not in ("user_id", "start_ts")},
        ).returning(models.Workout.id)
        workout_id = session.execute(stmt).scalar_one()
        session.execute(
            delete(models.WorkoutRecordSample).where(
                models.WorkoutRecordSample.workout_id == workout_id
            )
        )
        if w.records:
            session.execute(
                models.WorkoutRecordSample.__table__.insert(),
                [{"workout_id": workout_id, **rec} for rec in w.records],
            )
        n += 1
    return n
