"""Window resolution + counter evaluation.

Built strictly on top of the engine's per_date_status. Each counter slices its
own window (Dubai = calendar year, India = financial year) from the same map.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional, Set, Tuple

from . import engine
from .models import (
    MODE_LIMIT,
    MODE_TARGET,
    WINDOW_CALENDAR,
    WINDOW_FINANCIAL,
)


def resolve_window(window_type: str, as_of: date) -> Tuple[date, date]:
    """Return the inclusive [start, end] date range for a window at `as_of`.

    - calendar_year:  1 Jan .. 31 Dec of as_of's year.
    - financial_year: Indian FY (1 Apr .. 31 Mar) containing as_of.
    """
    if window_type == WINDOW_CALENDAR:
        return date(as_of.year, 1, 1), date(as_of.year, 12, 31)
    if window_type == WINDOW_FINANCIAL:
        if as_of.month >= 4:
            return date(as_of.year, 4, 1), date(as_of.year + 1, 3, 31)
        return date(as_of.year - 1, 4, 1), date(as_of.year, 3, 31)
    raise ValueError(f"Unknown window type: {window_type}")


def _warn_level(count: int, threshold: int, mode: str) -> str:
    """Visual state. For a limit: green -> amber (>=80%) -> red (>=100%).

    For a target: 'reached' once met, else 'progress'.
    """
    if threshold <= 0:
        return "neutral"
    ratio = count / threshold
    if mode == MODE_LIMIT:
        if ratio >= 1.0:
            return "red"
        if ratio >= 0.8:
            return "amber"
        return "green"
    # target_to_reach
    return "reached" if count >= threshold else "progress"


@dataclass
class CounterResult:
    key: str
    label: str
    country: str
    mode: str
    window: str
    window_start: date
    window_end: date
    count: int
    threshold: int
    pending: Optional[int]  # target_to_reach only: days still needed
    remaining_before_limit: Optional[int]  # limit_to_watch only
    warn_level: str
    allowance: Optional[int]  # target_to_reach only

    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "label": self.label,
            "country": self.country,
            "mode": self.mode,
            "window": self.window,
            "windowStart": self.window_start.isoformat(),
            "windowEnd": self.window_end.isoformat(),
            "count": self.count,
            "threshold": self.threshold,
            "pending": self.pending,
            "remainingBeforeLimit": self.remaining_before_limit,
            "warnLevel": self.warn_level,
            "allowance": self.allowance,
        }


def evaluate_counter(
    per_date: Dict[date, Set[str]],
    *,
    key: str,
    label: str,
    country: str,
    mode: str,
    threshold: int,
    window: str,
    as_of: date,
) -> CounterResult:
    """Evaluate one counter against the shared per_date map."""
    start, end = resolve_window(window, as_of)
    count = engine.count_country(per_date, country, start, end)

    pending: Optional[int] = None
    remaining_before_limit: Optional[int] = None
    allowance: Optional[int] = None

    if mode == MODE_TARGET:
        pending = max(0, threshold - count)
        # Allowance: how many more days can still be spent OUTSIDE the target
        # country and still reach the target before the window closes.
        #   daysRemaining = window_end - as_of   (clamped at 0)
        #   allowance     = daysRemaining - pending
        days_remaining = max(0, (end - as_of).days)
        allowance = days_remaining - pending
    elif mode == MODE_LIMIT:
        remaining_before_limit = max(0, threshold - count)

    return CounterResult(
        key=key,
        label=label,
        country=country,
        mode=mode,
        window=window,
        window_start=start,
        window_end=end,
        count=count,
        threshold=threshold,
        pending=pending,
        remaining_before_limit=remaining_before_limit,
        warn_level=_warn_level(count, threshold, mode),
        allowance=allowance,
    )
