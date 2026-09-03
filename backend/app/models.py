"""Normalized SQLAlchemy models.

Design note (refinement of the approved plan): rather than one mixed
``activity_sample`` table, each intraday metric gets its own narrow long-format
table ``(user_id, source, ts, value...)``. This matches both Garmin Connect's
per-metric endpoints and FIT's per-message split (they sample at different
cadences — HR every ~2 min, steps in 15-min buckets), and keeps charts trivial.
This is exactly the shape the schema research recommended.

Every ingest path (Garmin Connect pull, FIT upload, a future Gadgetbridge
SQLite adapter) converges on these tables. Natural unique keys make the two
sources merge idempotently (re-syncing never duplicates).
"""
from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Source(str, enum.Enum):
    garmin_connect = "garmin_connect"
    fit_upload = "fit_upload"  # FIT via web upload OR the desktop companion agent
    watch_ciq = "watch_ciq"  # on-watch Connect IQ app pushing live metrics
    gadgetbridge = "gadgetbridge"  # reserved for the future GB-SQLite adapter


class SleepStage(str, enum.Enum):
    awake = "awake"
    light = "light"
    deep = "deep"
    rem = "rem"
    unmeasured = "unmeasured"


# Reusable column types.
_source_col = Enum(Source, name="source_enum", native_enum=False, length=32)
_stage_col = Enum(SleepStage, name="sleep_stage_enum", native_enum=False, length=16)


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="me")


class DailySummary(Base):
    """One row per (user, calendar day) — powers the dashboard tiles."""

    __tablename__ = "daily_summary"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_daily_user_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    source: Mapped[Source] = mapped_column(_source_col)
    day: Mapped[date] = mapped_column(Date, index=True)

    steps: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[float | None] = mapped_column(Float)
    active_seconds: Mapped[int | None] = mapped_column(Integer)
    floors: Mapped[int | None] = mapped_column(Integer)
    calories: Mapped[int | None] = mapped_column(Integer)
    resting_hr: Mapped[int | None] = mapped_column(Integer)
    min_hr: Mapped[int | None] = mapped_column(Integer)
    max_hr: Mapped[int | None] = mapped_column(Integer)
    avg_stress: Mapped[int | None] = mapped_column(Integer)
    body_battery_high: Mapped[int | None] = mapped_column(Integer)
    body_battery_low: Mapped[int | None] = mapped_column(Integer)
    intensity_minutes: Mapped[int | None] = mapped_column(Integer)
    vo2max: Mapped[float | None] = mapped_column(Float)
    training_status: Mapped[str | None] = mapped_column(String(64))
    steps_goal: Mapped[int | None] = mapped_column(Integer)


class _Sample(Base):
    """Abstract base for narrow (user, ts, value) time-series tables."""

    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    source: Mapped[Source] = mapped_column(_source_col)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class HeartRateSample(_Sample):
    __tablename__ = "heart_rate_sample"
    __table_args__ = (UniqueConstraint("user_id", "ts", name="uq_hr_user_ts"),)
    bpm: Mapped[int] = mapped_column(Integer)


class StepsSample(_Sample):
    """Steps within a bucket beginning at ``ts`` (Garmin uses 15-min buckets)."""

    __tablename__ = "steps_sample"
    __table_args__ = (UniqueConstraint("user_id", "ts", name="uq_steps_user_ts"),)
    steps: Mapped[int] = mapped_column(Integer)
    activity_level: Mapped[str | None] = mapped_column(String(32))


class StressSample(_Sample):
    __tablename__ = "stress_sample"
    __table_args__ = (UniqueConstraint("user_id", "ts", name="uq_stress_user_ts"),)
    value: Mapped[int] = mapped_column(Integer)  # 0-100; <0 means unmeasured/at-rest


class Spo2Sample(_Sample):
    __tablename__ = "spo2_sample"
    __table_args__ = (UniqueConstraint("user_id", "ts", name="uq_spo2_user_ts"),)
    value: Mapped[int] = mapped_column(Integer)  # percent


class BodyBatterySample(_Sample):
    __tablename__ = "body_battery_sample"
    __table_args__ = (UniqueConstraint("user_id", "ts", name="uq_bb_user_ts"),)
    level: Mapped[int] = mapped_column(Integer)  # 0-100
    status: Mapped[str | None] = mapped_column(String(32))  # charging/draining


class RespirationSample(_Sample):
    __tablename__ = "respiration_sample"
    __table_args__ = (UniqueConstraint("user_id", "ts", name="uq_resp_user_ts"),)
    value: Mapped[float] = mapped_column(Float)  # breaths per minute


class HrvReading(_Sample):
    __tablename__ = "hrv_reading"
    __table_args__ = (UniqueConstraint("user_id", "ts", name="uq_hrv_user_ts"),)
    value_ms: Mapped[float] = mapped_column(Float)


class HrvSummary(Base):
    __tablename__ = "hrv_summary"
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_hrvsum_user_day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    source: Mapped[Source] = mapped_column(_source_col)
    day: Mapped[date] = mapped_column(Date, index=True)
    last_night_avg: Mapped[float | None] = mapped_column(Float)
    baseline_low: Mapped[float | None] = mapped_column(Float)
    baseline_high: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str | None] = mapped_column(String(32))


class SleepSession(Base):
    __tablename__ = "sleep_session"
    __table_args__ = (
        UniqueConstraint("user_id", "start_ts", name="uq_sleep_user_start"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    source: Mapped[Source] = mapped_column(_source_col)
    day: Mapped[date] = mapped_column(Date, index=True)  # the night's "wake" date
    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deep_s: Mapped[int | None] = mapped_column(Integer)
    light_s: Mapped[int | None] = mapped_column(Integer)
    rem_s: Mapped[int | None] = mapped_column(Integer)
    awake_s: Mapped[int | None] = mapped_column(Integer)
    total_s: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[int | None] = mapped_column(Integer)

    stages: Mapped[list["SleepStageSegment"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class SleepStageSegment(Base):
    __tablename__ = "sleep_stage_segment"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sleep_session.id", ondelete="CASCADE"), index=True
    )
    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stage: Mapped[SleepStage] = mapped_column(_stage_col)

    session: Mapped[SleepSession] = relationship(back_populates="stages")


class Workout(Base):
    """A recorded activity/workout. Keyed on (user, start_ts) so a Garmin Connect
    pull and a later FIT upload of the same session merge instead of duplicating."""

    __tablename__ = "workout"
    __table_args__ = (
        UniqueConstraint("user_id", "start_ts", name="uq_workout_user_start"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    source: Mapped[Source] = mapped_column(_source_col)
    external_id: Mapped[str | None] = mapped_column(String(64), index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    activity_type: Mapped[str | None] = mapped_column(String(64))
    start_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_s: Mapped[float | None] = mapped_column(Float)
    distance_m: Mapped[float | None] = mapped_column(Float)
    calories: Mapped[int | None] = mapped_column(Integer)
    avg_hr: Mapped[int | None] = mapped_column(Integer)
    max_hr: Mapped[int | None] = mapped_column(Integer)
    avg_speed: Mapped[float | None] = mapped_column(Float)
    ascent_m: Mapped[float | None] = mapped_column(Float)

    records: Mapped[list["WorkoutRecordSample"]] = relationship(
        back_populates="workout", cascade="all, delete-orphan"
    )


class WorkoutRecordSample(Base):
    __tablename__ = "workout_record_sample"
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    workout_id: Mapped[int] = mapped_column(
        ForeignKey("workout.id", ondelete="CASCADE"), index=True
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    hr: Mapped[int | None] = mapped_column(Integer)
    speed: Mapped[float | None] = mapped_column(Float)
    cadence: Mapped[float | None] = mapped_column(Float)
    altitude: Mapped[float | None] = mapped_column(Float)
    power: Mapped[float | None] = mapped_column(Float)
    temperature: Mapped[float | None] = mapped_column(Float)

    workout: Mapped[Workout] = relationship(back_populates="records")


# Tables that share the (user_id, ts) uniqueness contract, exposed for the
# generic upsert helper in app.ingest.base.
METRIC_TABLES = {
    "heart_rate": HeartRateSample,
    "steps": StepsSample,
    "stress": StressSample,
    "spo2": Spo2Sample,
    "body_battery": BodyBatterySample,
    "respiration": RespirationSample,
    "hrv": HrvReading,
}
