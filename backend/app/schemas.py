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


class EntryOut(BaseModel):
    id: int
    country: str
    from_date: date
    to_date: date
    source: str
    note: str


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
