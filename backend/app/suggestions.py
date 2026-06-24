"""Dynamic Dubai trip suggestion engine.

Generates a forward schedule of UAE trips to close the pending Dubai (target)
gap. Suggestions are ephemeral — they are NOT persisted; only accepted trips are
saved (as PlannedTrip). Derived entirely from engine counts.

Feature 2 makes the planner constraint-aware:
  - `blocked`  windows = India commitments the user is attending (mandatory). No
    UAE trip day may fall inside one — the planner schedules trips around them.
  - `prefer`   windows = travel-opportunity periods (e.g. school holidays). Trip
    starts are nudged toward these when it doesn't cost extra days.
Events themselves are never counted — they only shape the schedule.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

# A window is (start, end, label); endpoints inclusive.
Window = Tuple[date, date, str]


def _blocking(d: date, blocked: Sequence[Window]) -> Optional[Window]:
    """Return the blocked window containing `d`, if any."""
    for w in blocked:
        if w[0] <= d <= w[1]:
            return w
    return None


def _advance_past_blocks(d: date, blocked: Sequence[Window]) -> Tuple[date, Optional[str]]:
    """Move `d` forward until it is not inside any blocked window.

    Returns the free date and the label of the last window we jumped over (so the
    next trip can say "after <commitment>").
    """
    last_label: Optional[str] = None
    while True:
        w = _blocking(d, blocked)
        if w is None:
            return d, last_label
        d = w[1] + timedelta(days=1)
        last_label = w[2]


def _next_block_start_within(start: date, end: date, blocked: Sequence[Window]) -> Optional[Window]:
    """Earliest blocked window that begins within (start, end]; clips a trip short."""
    candidates = [w for w in blocked if start < w[0] <= end]
    return min(candidates, key=lambda w: w[0]) if candidates else None


def suggest_trips(
    *,
    pending: int,
    trip_len: int,
    min_gap_days: int,
    start_from: date,
    window_end: Optional[date] = None,
    blocked: Optional[Sequence[Window]] = None,
    prefer: Optional[Sequence[Window]] = None,
) -> List[Dict]:
    """Produce an ordered list of suggested UAE trips.

    Each trip is up to `trip_len` days long (inclusive), separated from the
    previous by `min_gap_days`. We stop once cumulative UAE days cover `pending`,
    or when trips would run past `window_end`. No trip day overlaps a `blocked`
    window; starts are nudged toward `prefer` windows.
    """
    trips: List[Dict] = []
    if pending <= 0 or trip_len <= 0:
        return trips

    blocked = sorted(blocked or [], key=lambda w: w[0])
    prefer = sorted(prefer or [], key=lambda w: w[0])

    remaining = pending
    cursor = start_from
    # Safety bound: never propose more trips than days needed (each trip >=1 day).
    max_trips = pending + 1

    while remaining > 0 and len(trips) < max_trips:
        trip_start, after_label = _advance_past_blocks(cursor, blocked)

        # Nudge the start into an upcoming travel-opportunity window if it begins
        # soon (within one trip's reach) and isn't itself blocked.
        prefer_label: Optional[str] = None
        for ps, pe, plabel in prefer:
            if pe < trip_start:
                continue
            snapped = max(trip_start, ps)
            if ps <= trip_start <= pe:  # already inside a prefer window
                prefer_label = plabel
                break
            if trip_start < ps <= trip_start + timedelta(days=trip_len):
                cand, _ = _advance_past_blocks(snapped, blocked)
                if cand <= pe:
                    trip_start = cand
                    prefer_label = plabel
                    after_label = None
                break

        if window_end is not None and trip_start > window_end:
            break

        days_this_trip = min(trip_len, remaining)
        trip_end = trip_start + timedelta(days=days_this_trip - 1)

        # Clip if a commitment starts mid-trip.
        clip = _next_block_start_within(trip_start, trip_end, blocked)
        clipped_label: Optional[str] = None
        if clip is not None:
            trip_end = clip[0] - timedelta(days=1)
            days_this_trip = (trip_end - trip_start).days + 1
            clipped_label = clip[2]

        # Clip to the target window's close.
        if window_end is not None and trip_end > window_end:
            trip_end = window_end
            days_this_trip = (trip_end - trip_start).days + 1
        if days_this_trip <= 0:
            break

        remaining = max(0, remaining - days_this_trip)

        note_bits = []
        if after_label:
            note_bits.append(f"after {after_label}")
        if prefer_label:
            note_bits.append(f"during {prefer_label}")
        if clipped_label:
            note_bits.append(f"back before {clipped_label}")

        trips.append(
            {
                "country": "AE",
                "from": trip_start.isoformat(),
                "to": trip_end.isoformat(),
                "days": days_this_trip,
                "pendingAfter": remaining,
                "note": ", ".join(note_bits),
            }
        )
        # Next trip starts after the gap.
        cursor = trip_end + timedelta(days=min_gap_days + 1)

    return trips
