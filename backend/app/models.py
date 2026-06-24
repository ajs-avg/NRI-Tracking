"""SQLAlchemy ORM models — MVP Phase 1 (simplified persistence).

Persisted: Person, ManualEntry, CounterConfig, Settings, PlannedTrip (accepted only).
Suggested trips are generated dynamically and NOT stored.
Future GPS phase will add a LocationPing source feeding the same counting engine.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# Country codes used across the app.
COUNTRY_INDIA = "IN"
COUNTRY_UAE = "AE"

# Counter modes.
MODE_TARGET = "target_to_reach"
MODE_LIMIT = "limit_to_watch"

# Window types.
WINDOW_CALENDAR = "calendar_year"
WINDOW_FINANCIAL = "financial_year"

# Commitment event types (Feature 2).
EVENT_MANDATORY = "mandatory"  # must be in `country` (e.g. wedding, school function)
EVENT_OPTIONAL = "optional"  # neutral
EVENT_TRAVEL_OPPORTUNITY = "travel_opportunity"  # easier to travel (e.g. school holidays)


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True, index=True)  # NKA|KKA|HKA
    name: Mapped[str] = mapped_column(String(120), default="")

    entries: Mapped[list["ManualEntry"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    counters: Mapped[list["CounterConfig"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    settings: Mapped["Settings"] = relationship(
        back_populates="person", cascade="all, delete-orphan", uselist=False
    )
    trips: Mapped[list["PlannedTrip"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    events: Mapped[list["CommitmentEvent"]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )


class ManualEntry(Base):
    """A range of days the person was in a country. Endpoints are INCLUSIVE."""

    __tablename__ = "manual_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"), index=True)
    country: Mapped[str] = mapped_column(String(2))  # IN|AE
    from_date: Mapped[date] = mapped_column(Date)
    to_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(16), default="manual")
    note: Mapped[str] = mapped_column(String(255), default="")
    # Informational only — the engine counts by DATE, never by time. These let the
    # user record the real clock time (e.g. immigration cleared 00:10 next day) so
    # they can decide which calendar date the entry belongs to. "HH:MM" or null.
    dep_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True, default=None)
    arr_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True, default=None)

    person: Mapped["Person"] = relationship(back_populates="entries")


class CounterConfig(Base):
    """Generalized counter: target_to_reach (Dubai) or limit_to_watch (India)."""

    __tablename__ = "counter_configs"
    __table_args__ = (UniqueConstraint("person_id", "key", name="uq_person_counter"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"), index=True)
    key: Mapped[str] = mapped_column(String(16))  # dubai|india
    label: Mapped[str] = mapped_column(String(40), default="")
    country: Mapped[str] = mapped_column(String(2))  # IN|AE
    mode: Mapped[str] = mapped_column(String(20))  # target_to_reach|limit_to_watch
    threshold: Mapped[int] = mapped_column(Integer)
    window: Mapped[str] = mapped_column(String(20))  # calendar_year|financial_year

    person: Mapped["Person"] = relationship(back_populates="counters")


class Settings(Base):
    __tablename__ = "settings"

    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"), primary_key=True)
    default_trip_len: Mapped[int] = mapped_column(Integer, default=18)
    min_gap_days: Mapped[int] = mapped_column(Integer, default=14)

    person: Mapped["Person"] = relationship(back_populates="settings")


class PlannedTrip(Base):
    """Persisted ONLY after a suggestion is accepted."""

    __tablename__ = "planned_trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"), index=True)
    country: Mapped[str] = mapped_column(String(2), default=COUNTRY_UAE)
    from_date: Mapped[date] = mapped_column(Date)
    to_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="accepted")

    person: Mapped["Person"] = relationship(back_populates="trips")


class CommitmentEvent(Base):
    """A personal/professional commitment that the trip planner reasons about.

    Events are PLANNING CONSTRAINTS ONLY — they never feed the counting engine
    (events != coverage). A `mandatory` + `attend=True` + India event is a blackout
    window the planner must avoid; a `travel_opportunity` window is a preferred slot
    for UAE trips. `attend=None` means the user hasn't answered yet (drives the
    "will you attend?" prompt).
    """

    __tablename__ = "commitment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("persons.id"), index=True)
    title: Mapped[str] = mapped_column(String(160), default="")
    country: Mapped[str] = mapped_column(String(6), default=COUNTRY_INDIA)  # IN|AE|OTHER
    from_date: Mapped[date] = mapped_column(Date)
    to_date: Mapped[date] = mapped_column(Date)
    event_type: Mapped[str] = mapped_column(String(20), default=EVENT_MANDATORY)
    attend: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, default=None)
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual|csv
    note: Mapped[str] = mapped_column(String(255), default="")

    person: Mapped["Person"] = relationship(back_populates="events")
