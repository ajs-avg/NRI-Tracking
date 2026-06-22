"""Counting engine — the SINGLE SOURCE OF TRUTH for all day counts.

Everything (dashboard, calendar, suggestions, allowance) derives from
`per_date_status`. The engine knows nothing about windows, counters, or HTTP;
it just turns a set of inclusive country-coverage intervals into a per-date map
of which countries are credited.

Core rule:
  - A date is credited to EVERY country whose interval covers it.
  - Interval endpoints are INCLUSIVE.
  - Two intervals sharing a boundary date -> that date is credited to BOTH
    countries -> a "travel day".
  - A date with no coverage -> UNKNOWN.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, Iterator, List, Set


@dataclass(frozen=True)
class Interval:
    """An inclusive [start, end] span during which a person was in `country`."""

    country: str
    start: date
    end: date


def daterange(start: date, end: date) -> Iterator[date]:
    """Yield every date from start to end inclusive."""
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def per_date_status(
    intervals: Iterable[Interval], start: date, end: date
) -> Dict[date, Set[str]]:
    """Map each date in [start, end] to the set of countries credited that day.

    Empty set == UNKNOWN (no coverage). This is the canonical structure all
    higher-level counts are built from.
    """
    result: Dict[date, Set[str]] = {d: set() for d in daterange(start, end)}
    for iv in intervals:
        lo = max(iv.start, start)
        hi = min(iv.end, end)
        if lo > hi:
            continue
        for d in daterange(lo, hi):
            result[d].add(iv.country)
    return result


def count_country(
    per_date: Dict[date, Set[str]], country: str, start: date, end: date
) -> int:
    """Days within [start, end] credited to `country`."""
    return sum(
        1 for d in daterange(start, end) if country in per_date.get(d, set())
    )


def count_travel_days(
    per_date: Dict[date, Set[str]], start: date, end: date
) -> int:
    """Days within [start, end] credited to 2+ countries."""
    return sum(
        1 for d in daterange(start, end) if len(per_date.get(d, set())) >= 2
    )


def count_unknown_days(
    per_date: Dict[date, Set[str]], start: date, end: date, as_of: date
) -> int:
    """Past (<= as_of) days within [start, end] that have no coverage.

    Future days with no coverage are simply "not yet recorded", not unknown.
    """
    hi = min(end, as_of)
    if start > hi:
        return 0
    return sum(1 for d in daterange(start, hi) if not per_date.get(d, set()))


def day_status_label(countries: Set[str], d: date, as_of: date) -> str:
    """Calendar status for a single date: india | uae | both | unknown | future."""
    from .models import COUNTRY_INDIA, COUNTRY_UAE

    if len(countries) >= 2:
        return "both"
    if COUNTRY_UAE in countries:
        return "uae"
    if COUNTRY_INDIA in countries:
        return "india"
    # No coverage.
    if d > as_of:
        return "future"
    return "unknown"


def intervals_from_rows(rows: List) -> List[Interval]:
    """Build engine Intervals from ManualEntry / PlannedTrip ORM rows.

    Both row types expose `.country`, `.from_date`, `.to_date`, so this is the
    single adapter that lets manual entries and accepted trips (and, later, GPS
    data) feed the same engine.
    """
    return [Interval(r.country, r.from_date, r.to_date) for r in rows]
