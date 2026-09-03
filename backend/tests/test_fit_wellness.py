"""Unit tests for the wellness/sleep handlers in FitIngester.

These do not need a real FIT file: they drive the message handlers directly with
small fake `frame` objects that mimic fitdecode's ``get_value(field, fallback)``
API. They cover the parts of the parser that we can't exercise with the sample
ACTIVITY files (MONITOR steps differencing, SpO2, respiration, sleep stages).

Run: pytest backend/tests/test_fit_wellness.py
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.ingest.fit import FIT_EPOCH, FitIngester
from app.models import SleepStage


class FakeFrame:
    """Mimics a fitdecode data frame for the fields our handlers read."""

    def __init__(self, name, **values):
        self.name = name
        self._values = values

    def get_value(self, field, fallback=None):
        return self._values.get(field, fallback)


def _fit_ts(dt: datetime) -> int:
    """A datetime -> FIT seconds-since-1989 (what a fitdecode int field holds)."""
    return int(dt.timestamp()) - FIT_EPOCH


def test_monitoring_steps_are_differenced_per_day():
    ing = FitIngester()
    bundle_steps = []

    class B:  # minimal bundle stand-in
        steps = bundle_steps
        heart_rate = []
        respiration = []
        spo2 = []

    b = B()
    state = {"day": None, "last": None}
    base = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    # cumulative counter across the day: 100, 250, 250, 400
    for mins, cum in [(0, 100), (15, 250), (30, 250), (45, 400)]:
        ts = base.replace(minute=mins)
        f = FakeFrame("monitoring", timestamp=_fit_ts(ts), steps=cum)
        ing._monitoring(f, b, None, state)
    # opening bucket 100, then deltas 150, 0(skipped), 150
    assert [s["steps"] for s in bundle_steps] == [100, 150, 150]


def test_monitoring_step_counter_reset_rebaselines():
    ing = FitIngester()

    class B:
        steps = []
        heart_rate = []
        respiration = []
        spo2 = []

    b = B()
    state = {"day": None, "last": None}
    base = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    for mins, cum in [(0, 500), (15, 200)]:  # decrease = reset
        ts = base.replace(minute=mins)
        ing._monitoring(FakeFrame("monitoring", timestamp=_fit_ts(ts), steps=cum), b, None, state)
    # 500 opening, then reset -> delta treated as the new value 200
    assert [s["steps"] for s in b.steps] == [500, 200]


def test_monitoring_emits_hr_respiration_spo2():
    ing = FitIngester()

    class B:
        steps = []
        heart_rate = []
        respiration = []
        spo2 = []

    b = B()
    ts = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    f = FakeFrame("monitoring", timestamp=_fit_ts(ts), heart_rate=61,
                  respiration_rate=14.5, reading_spo2=96)
    ing._monitoring(f, b, None, {"day": None, "last": None})
    assert b.heart_rate[0]["bpm"] == 61
    assert b.respiration[0]["value"] == 14.5
    assert b.spo2[0]["value"] == 96


def test_spo2_and_respiration_guards():
    ing = FitIngester()

    class B:
        spo2 = []
        respiration = []

    b = B()
    ts = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
    ing._spo2(FakeFrame("spo2", timestamp=_fit_ts(ts), reading_spo2=0), b)   # dropped
    ing._spo2(FakeFrame("spo2", timestamp=_fit_ts(ts), reading_spo2=94), b)  # kept
    ing._respiration(FakeFrame("respiration_rate", timestamp=_fit_ts(ts), respiration_rate=0), b)   # dropped
    ing._respiration(FakeFrame("respiration_rate", timestamp=_fit_ts(ts), respiration_rate=13.2), b)  # kept
    assert [s["value"] for s in b.spo2] == [94]
    assert [s["value"] for s in b.respiration] == [13.2]


def test_sleep_assembly_from_levels():
    ing = FitIngester()

    class B:
        sleep = []

    b = B()
    segs = []
    base = datetime(2026, 9, 1, 23, 0, tzinfo=timezone.utc)
    # light 30m, deep 30m, rem 30m
    rem_ts = datetime(2026, 9, 2, 0, 0, tzinfo=timezone.utc)
    ing._sleep_level(FakeFrame("sleep_level", timestamp=_fit_ts(base), sleep_level="light"), segs)
    ing._sleep_level(FakeFrame("sleep_level", timestamp=_fit_ts(base.replace(minute=30)), sleep_level="deep"), segs)
    ing._sleep_level(FakeFrame("sleep_level", timestamp=_fit_ts(rem_ts), sleep_level="rem"), segs)
    ing._assemble_sleep(b, segs, {})
    assert len(b.sleep) == 1
    s = b.sleep[0]
    assert [seg.stage for seg in s.stages] == [SleepStage.light, SleepStage.deep, SleepStage.rem]
    assert s.light_s == 1800 and s.deep_s == 1800  # rem is the last (5-min tail)
    assert s.day == datetime(2026, 9, 2).date()


def test_sleep_assessment_summary_overrides_segments():
    ing = FitIngester()

    class B:
        sleep = []

    b = B()
    segs = []
    base = datetime(2026, 9, 1, 23, 0, tzinfo=timezone.utc)
    ing._sleep_level(FakeFrame("sleep_level", timestamp=_fit_ts(base), sleep_level="light"), segs)
    summary = {}
    ing._sleep_assessment(
        FakeFrame("sleep_assessment", total_deep_sleep_time=3600,
                  total_light_sleep_time=7200, overall_sleep_score=82), summary)
    ing._assemble_sleep(b, segs, summary)
    s = b.sleep[0]
    assert s.deep_s == 3600 and s.light_s == 7200 and s.score == 82
