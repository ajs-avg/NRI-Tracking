"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import date
from datetime import date as _Date  # alias to avoid shadowing in TicketSegmentIn
from typing import List, Optional

from pydantic import BaseModel, field_validator


class PersonOut(BaseModel):
    id: int
    code: str
    name: str


class EntryIn(BaseModel):
    country: str  # IN | AE
    from_date: date
    to_date: date
    note: str = ""
    dep_time: Optional[str] = None  # "HH:MM" — informational only
    arr_time: Optional[str] = None  # "HH:MM" — informational only

    @field_validator("country")
    @classmethod
    def _country_ok(cls, v: str) -> str:
        if v not in ("IN", "AE"):
            raise ValueError("country must be IN or AE")
        return v

    @field_validator("to_date")
    @classmethod
    def _range_ok(cls, v: date, info) -> date:
        start = info.data.get("from_date")
        if start is not None and v < start:
            raise ValueError("to_date must be >= from_date")
        return v


class EntryUpdate(BaseModel):
    """Partial edit of a committed entry (Feature 1 — fix arrival date/time)."""

    country: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    note: Optional[str] = None
    dep_time: Optional[str] = None
    arr_time: Optional[str] = None

    @field_validator("country")
    @classmethod
    def _country_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("IN", "AE"):
            raise ValueError("country must be IN or AE")
        return v


class EntryOut(BaseModel):
    id: int
    country: str
    from_date: date
    to_date: date
    source: str
    note: str
    dep_time: Optional[str] = None
    arr_time: Optional[str] = None


class CounterConfigIn(BaseModel):
    key: str
    label: str
    country: str
    mode: str  # target_to_reach | limit_to_watch
    threshold: int
    window: str  # calendar_year | financial_year


class CounterConfigOut(CounterConfigIn):
    id: int


class SettingsIn(BaseModel):
    default_trip_len: int = 18
    min_gap_days: int = 14


class SettingsOut(SettingsIn):
    person_id: int


class TicketSegmentIn(BaseModel):
    date: Optional[_Date] = None
    from_airport: str = ""
    to_airport: str = ""
    from_country: str  # IN | AE | OTHER
    to_country: str
    flight_no: str = ""
    dep_time: Optional[str] = None  # "HH:MM" 24h, from the ticket
    arr_time: Optional[str] = None  # "HH:MM" 24h, from the ticket


class TicketCommitIn(BaseModel):
    segments: List[TicketSegmentIn]


class TripAcceptIn(BaseModel):
    country: str = "AE"
    from_date: date
    to_date: date


class TripOut(BaseModel):
    id: int
    country: str
    from_date: date
    to_date: date
    status: str


_EVENT_TYPES = ("mandatory", "optional", "travel_opportunity")


class EventIn(BaseModel):
    title: str = ""
    country: str = "IN"  # IN | AE | OTHER
    from_date: date
    to_date: date
    event_type: str = "mandatory"
    attend: Optional[bool] = None
    note: str = ""

    @field_validator("country")
    @classmethod
    def _country_ok(cls, v: str) -> str:
        if v not in ("IN", "AE", "OTHER"):
            raise ValueError("country must be IN, AE or OTHER")
        return v

    @field_validator("event_type")
    @classmethod
    def _type_ok(cls, v: str) -> str:
        if v not in _EVENT_TYPES:
            raise ValueError(f"event_type must be one of {_EVENT_TYPES}")
        return v

    @field_validator("to_date")
    @classmethod
    def _range_ok(cls, v: date, info) -> date:
        start = info.data.get("from_date")
        if start is not None and v < start:
            raise ValueError("to_date must be >= from_date")
        return v


class EventUpdate(BaseModel):
    """Partial edit — also used by the RSVP toggle (just `attend`)."""

    title: Optional[str] = None
    country: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    event_type: Optional[str] = None
    attend: Optional[bool] = None
    note: Optional[str] = None

    @field_validator("country")
    @classmethod
    def _country_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("IN", "AE", "OTHER"):
            raise ValueError("country must be IN, AE or OTHER")
        return v

    @field_validator("event_type")
    @classmethod
    def _type_ok(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in _EVENT_TYPES:
            raise ValueError(f"event_type must be one of {_EVENT_TYPES}")
        return v


class EventOut(BaseModel):
    id: int
    title: str
    country: str
    from_date: date
    to_date: date
    event_type: str
    attend: Optional[bool]
    source: str
    note: str


class GoogleStatusOut(BaseModel):
    configured: bool          # are the server's Google OAuth env vars set?
    connected: bool           # has this person linked a Google account?
    email: str = ""
    last_synced: Optional[str] = None


class GoogleSyncOut(BaseModel):
    entries_created: int = 0      # new presence rows (ManualEntry)
    entries_updated: int = 0
    events_created: int = 0       # new commitment rows (CommitmentEvent)
    events_updated: int = 0
    scanned: int = 0              # raw Google events looked at
    skipped: int = 0             # events with no usable signal
    last_synced: Optional[str] = None
