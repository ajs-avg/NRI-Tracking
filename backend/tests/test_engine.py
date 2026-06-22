"""Unit tests for the counting engine + counter math (single source of truth)."""
from __future__ import annotations

from datetime import date

from app import engine
from app.counters import evaluate_counter, resolve_window
from app.models import (
    MODE_LIMIT,
    MODE_TARGET,
    WINDOW_CALENDAR,
    WINDOW_FINANCIAL,
)
from app.suggestions import suggest_trips

IN = "IN"
AE = "AE"


def _iv(country, s, e):
    return engine.Interval(country, date.fromisoformat(s), date.fromisoformat(e))


def test_inclusive_range_coverage():
    pd = engine.per_date_status(
        [_iv(AE, "2026-08-01", "2026-08-10")],
        date(2026, 8, 1),
        date(2026, 8, 31),
    )
    # 1..10 inclusive == 10 days.
    assert engine.count_country(pd, AE, date(2026, 8, 1), date(2026, 8, 31)) == 10
    assert AE in pd[date(2026, 8, 1)]
    assert AE in pd[date(2026, 8, 10)]
    assert AE not in pd[date(2026, 8, 11)]


def test_travel_day_shared_boundary():
    # India 1-10 Aug, UAE 10-20 Aug -> 10 Aug credited to BOTH.
    pd = engine.per_date_status(
        [_iv(IN, "2026-08-01", "2026-08-10"), _iv(AE, "2026-08-10", "2026-08-20")],
        date(2026, 8, 1),
        date(2026, 8, 31),
    )
    assert pd[date(2026, 8, 10)] == {IN, AE}
    assert engine.count_country(pd, IN, date(2026, 8, 1), date(2026, 8, 31)) == 10
    assert engine.count_country(pd, AE, date(2026, 8, 1), date(2026, 8, 31)) == 11
    assert engine.count_travel_days(pd, date(2026, 8, 1), date(2026, 8, 31)) == 1
    assert engine.day_status_label(pd[date(2026, 8, 10)], date(2026, 8, 10), date(2026, 12, 31)) == "both"


def test_unknown_days_only_in_past():
    as_of = date(2026, 8, 15)
    pd = engine.per_date_status(
        [_iv(AE, "2026-08-01", "2026-08-05")],
        date(2026, 8, 1),
        date(2026, 8, 31),
    )
    # 6..15 are past uncovered = 10 unknown; 16..31 are future, not unknown.
    assert engine.count_unknown_days(pd, date(2026, 8, 1), date(2026, 8, 31), as_of) == 10
    assert engine.day_status_label(set(), date(2026, 8, 20), as_of) == "future"
    assert engine.day_status_label(set(), date(2026, 8, 10), as_of) == "unknown"


def test_window_resolution():
    assert resolve_window(WINDOW_CALENDAR, date(2026, 8, 15)) == (
        date(2026, 1, 1),
        date(2026, 12, 31),
    )
    # Financial year: Aug 2026 -> FY Apr 2026..Mar 2027.
    assert resolve_window(WINDOW_FINANCIAL, date(2026, 8, 15)) == (
        date(2026, 4, 1),
        date(2027, 3, 31),
    )
    # Financial year: Feb 2026 -> FY Apr 2025..Mar 2026.
    assert resolve_window(WINDOW_FINANCIAL, date(2026, 2, 15)) == (
        date(2025, 4, 1),
        date(2026, 3, 31),
    )


def test_allowance_matches_client_example():
    # Client example: Dubai 78/190, daysRemaining 176 -> allowance 64.
    # Pick as_of so that Dec31 - as_of = 176 days.  Dec31 2026 minus 176 days.
    as_of = date(2026, 12, 31) - __import__("datetime").timedelta(days=176)
    # Build coverage giving exactly 78 UAE days in the calendar year up to as_of.
    start = date(2026, 1, 1)
    end = start + __import__("datetime").timedelta(days=77)  # 78 inclusive days
    pd = engine.per_date_status(
        [engine.Interval(AE, start, end)], date(2026, 1, 1), date(2026, 12, 31)
    )
    res = evaluate_counter(
        pd,
        key="dubai",
        label="Dubai Days",
        country=AE,
        mode=MODE_TARGET,
        threshold=190,
        window=WINDOW_CALENDAR,
        as_of=as_of,
    )
    assert res.count == 78
    assert res.pending == 112
    assert res.allowance == 64


def test_limit_warn_levels():
    pd = engine.per_date_status(
        [engine.Interval(IN, date(2026, 4, 1), date(2026, 9, 1))],
        date(2026, 4, 1),
        date(2027, 3, 31),
    )
    res = evaluate_counter(
        pd,
        key="india",
        label="India Days",
        country=IN,
        mode=MODE_LIMIT,
        threshold=175,
        window=WINDOW_FINANCIAL,
        as_of=date(2026, 9, 1),
    )
    # Apr 1 .. Sep 1 inclusive = 154 days. remaining = 175 - 154 = 21.
    assert res.count == 154
    assert res.remaining_before_limit == 21
    assert res.warn_level == "amber"  # 154/175 = 0.88 >= 0.8


def test_suggestions_descending_pending():
    trips = suggest_trips(
        pending=90,
        trip_len=18,
        min_gap_days=14,
        start_from=date(2026, 6, 22),
        window_end=date(2026, 12, 31),
    )
    assert len(trips) == 5  # 90 / 18 = 5 trips
    pendings = [t["pendingAfter"] for t in trips]
    assert pendings == [72, 54, 36, 18, 0]
    assert all(t["days"] == 18 for t in trips)
