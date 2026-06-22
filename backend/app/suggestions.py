"""Dynamic Dubai trip suggestion engine.

Generates a forward schedule of UAE trips to close the pending Dubai (target)
gap. Suggestions are ephemeral — they are NOT persisted; only accepted trips are
saved (as PlannedTrip). Derived entirely from engine counts.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional


def suggest_trips(
    *,
    pending: int,
    trip_len: int,
    min_gap_days: int,
    start_from: date,
    window_end: Optional[date] = None,
) -> List[Dict]:
    """Produce an ordered list of suggested UAE trips.

    Each trip is `trip_len` days long (inclusive), separated from the previous
    one by `min_gap_days`. We stop once the cumulative UAE days cover `pending`,
    or when trips would run past `window_end` (the target window's close).
    """
    trips: List[Dict] = []
    if pending <= 0 or trip_len <= 0:
        return trips

    remaining = pending
    cursor = start_from
    # Safety bound: never propose more trips than could possibly be needed.
    max_trips = pending + 1

    while remaining > 0 and len(trips) < max_trips:
        trip_start = cursor
        # Trip covers `trip_len` inclusive days -> end = start + (len - 1).
        days_this_trip = min(trip_len, remaining)
        trip_end = trip_start + timedelta(days=days_this_trip - 1)

        if window_end is not None and trip_start > window_end:
            break
        if window_end is not None and trip_end > window_end:
            trip_end = window_end
            days_this_trip = (trip_end - trip_start).days + 1
            if days_this_trip <= 0:
                break

        remaining = max(0, remaining - days_this_trip)
        trips.append(
            {
                "country": "AE",
                "from": trip_start.isoformat(),
                "to": trip_end.isoformat(),
                "days": days_this_trip,
                "pendingAfter": remaining,
            }
        )
        # Next trip starts after the gap.
        cursor = trip_end + timedelta(days=min_gap_days + 1)

    return trips
