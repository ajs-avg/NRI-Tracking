"""FastAPI app — wires the counting engine to HTTP for 3 fixed users.

All counts derive from the engine; no counting logic lives here.
"""
from __future__ import annotations

import calendar as _cal
import csv
import io
import os
from datetime import date
from typing import List, Optional, Tuple

from dotenv import load_dotenv

# Load backend/.env so GEMINI_API_KEY etc. are available when running locally.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import engine
from .counters import evaluate_counter
from .database import get_db
from .models import (
    CommitmentEvent,
    CounterConfig,
    ManualEntry,
    Person,
    PlannedTrip,
    Settings,
)
from .schemas import (
    CounterConfigIn,
    CounterConfigOut,
    EntryIn,
    EntryOut,
    EntryUpdate,
    EventIn,
    EventOut,
    EventUpdate,
    PersonOut,
    SettingsIn,
    SettingsOut,
    TicketCommitIn,
    TripAcceptIn,
    TripOut,
)
from .seed import init_db
from .suggestions import suggest_trips
from .tickets import TicketAnalysisError, analyze_ticket_image

app = FastAPI(title="NRI Residency Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _get_person(db: Session, person_id: int) -> Person:
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


def _coverage_intervals(db: Session, person_id: int) -> List[engine.Interval]:
    """All country-coverage data for a person: manual entries + accepted trips.

    This is the single point where data sources are merged before reaching the
    engine — future GPS data plugs in here without touching the engine itself.
    """
    entries = (
        db.query(ManualEntry).filter(ManualEntry.person_id == person_id).all()
    )
    trips = (
        db.query(PlannedTrip)
        .filter(PlannedTrip.person_id == person_id)
        .filter(PlannedTrip.status == "accepted")
        .all()
    )
    return engine.intervals_from_rows(entries) + engine.intervals_from_rows(trips)


def _parse_as_of(as_of: Optional[str]) -> date:
    if as_of is None:
        return date.today()
    try:
        return date.fromisoformat(as_of)
    except ValueError:
        raise HTTPException(status_code=400, detail="as_of must be YYYY-MM-DD")


# --------------------------------------------------------------------------- #
# Persons
# --------------------------------------------------------------------------- #
@app.get("/persons", response_model=List[PersonOut])
def list_persons(db: Session = Depends(get_db)):
    return db.query(Person).order_by(Person.id).all()


# --------------------------------------------------------------------------- #
# Summary (dashboard)
# --------------------------------------------------------------------------- #
@app.get("/persons/{person_id}/summary")
def summary(
    person_id: int,
    as_of: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    _get_person(db, person_id)
    ref = _parse_as_of(as_of)
    configs = (
        db.query(CounterConfig)
        .filter(CounterConfig.person_id == person_id)
        .order_by(CounterConfig.id)
        .all()
    )
    settings = db.get(Settings, person_id)
    intervals = _coverage_intervals(db, person_id)

    # Build a per_date map spanning the union of every counter window so each
    # counter (and the travel/unknown overview) reads from one shared structure.
    from .counters import resolve_window

    spans = [resolve_window(c.window, ref) for c in configs]
    if spans:
        span_start = min(s for s, _ in spans)
        span_end = max(e for _, e in spans)
    else:
        span_start, span_end = date(ref.year, 1, 1), date(ref.year, 12, 31)
    per_date = engine.per_date_status(intervals, span_start, span_end)

    counters = [
        evaluate_counter(
            per_date,
            key=c.key,
            label=c.label,
            country=c.country,
            mode=c.mode,
            threshold=c.threshold,
            window=c.window,
            as_of=ref,
        ).to_dict()
        for c in configs
    ]

    travel_days = engine.count_travel_days(per_date, span_start, span_end)
    unknown_days = engine.count_unknown_days(per_date, span_start, span_end, ref)

    return {
        "asOf": ref.isoformat(),
        "counters": counters,
        "travelDays": travel_days,
        "unknownDays": unknown_days,
        "incomplete": unknown_days > 0,
        "settings": {
            "defaultTripLen": settings.default_trip_len if settings else 18,
            "minGapDays": settings.min_gap_days if settings else 14,
        },
    }


# --------------------------------------------------------------------------- #
# Calendar
# --------------------------------------------------------------------------- #
@app.get("/persons/{person_id}/calendar")
def calendar_month(
    person_id: int,
    month: str = Query(..., description="YYYY-MM"),
    as_of: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    _get_person(db, person_id)
    ref = _parse_as_of(as_of)
    try:
        year_s, month_s = month.split("-")
        year, mon = int(year_s), int(month_s)
        first = date(year, mon, 1)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")
    last = date(year, mon, _cal.monthrange(year, mon)[1])

    intervals = _coverage_intervals(db, person_id)
    per_date = engine.per_date_status(intervals, first, last)

    days = []
    for d in engine.daterange(first, last):
        countries = per_date.get(d, set())
        days.append(
            {
                "date": d.isoformat(),
                "status": engine.day_status_label(countries, d, ref),
                "countries": sorted(countries),
            }
        )
    return {"month": month, "days": days}


# --------------------------------------------------------------------------- #
# Manual entries
# --------------------------------------------------------------------------- #
@app.get("/persons/{person_id}/entries", response_model=List[EntryOut])
def list_entries(person_id: int, db: Session = Depends(get_db)):
    _get_person(db, person_id)
    return (
        db.query(ManualEntry)
        .filter(ManualEntry.person_id == person_id)
        .order_by(ManualEntry.from_date)
        .all()
    )


@app.post("/persons/{person_id}/entries", response_model=EntryOut, status_code=201)
def create_entry(person_id: int, body: EntryIn, db: Session = Depends(get_db)):
    _get_person(db, person_id)
    entry = ManualEntry(
        person_id=person_id,
        country=body.country,
        from_date=body.from_date,
        to_date=body.to_date,
        note=body.note,
        dep_time=body.dep_time,
        arr_time=body.arr_time,
        source="manual",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@app.patch("/entries/{entry_id}", response_model=EntryOut)
def update_entry(entry_id: int, body: EntryUpdate, db: Session = Depends(get_db)):
    """Edit a committed entry — used to correct the arrival date/time when the real
    immigration day differs from the printed flight date (Feature 1)."""
    entry = db.get(ManualEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    data = body.model_dump(exclude_unset=True)
    for field in ("country", "from_date", "to_date", "note", "dep_time", "arr_time"):
        if field in data:
            setattr(entry, field, data[field])
    if entry.to_date < entry.from_date:
        raise HTTPException(status_code=400, detail="to_date must be >= from_date")

    db.commit()
    db.refresh(entry)
    return entry


@app.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(ManualEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()


# --------------------------------------------------------------------------- #
# Ticket AI analysis (upload images -> extract flights -> review -> commit)
# --------------------------------------------------------------------------- #
MAX_TICKETS = 20


@app.post("/persons/{person_id}/tickets/analyze")
def analyze_tickets(
    person_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Analyse up to 20 ticket images with Claude vision. Nothing is persisted —
    the extracted segments are returned for the user to review and confirm."""
    _get_person(db, person_id)
    if len(files) > MAX_TICKETS:
        raise HTTPException(status_code=400, detail=f"Max {MAX_TICKETS} tickets at once")

    results = []
    for f in files:
        media_type = f.content_type or "image/jpeg"
        if not media_type.startswith("image/"):
            results.append({"filename": f.filename, "error": "Not an image", "segments": []})
            continue
        data = f.file.read()
        try:
            segments = analyze_ticket_image(data, media_type)
            results.append({"filename": f.filename, "segments": segments})
        except TicketAnalysisError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        except Exception as exc:  # surface model/API errors per file, keep others
            results.append({"filename": f.filename, "error": str(exc), "segments": []})
    return {"results": results}


@app.post("/persons/{person_id}/tickets/commit", status_code=201)
def commit_tickets(
    person_id: int,
    body: TicketCommitIn,
    db: Session = Depends(get_db),
):
    """Turn reviewed flight segments into ManualEntry rows. Each flight date is a
    travel day: the date is credited to both the origin and destination country
    (single-day entries). OTHER countries are skipped (not tracked)."""
    _get_person(db, person_id)
    created = 0
    for seg in body.segments:
        if seg.date is None:
            continue
        for country in {seg.from_country, seg.to_country}:
            if country not in ("IN", "AE"):
                continue
            db.add(
                ManualEntry(
                    person_id=person_id,
                    country=country,
                    from_date=seg.date,
                    to_date=seg.date,
                    source="ticket",
                    note=f"{seg.from_airport}→{seg.to_airport} {seg.flight_no}".strip(),
                    dep_time=seg.dep_time,
                    arr_time=seg.arr_time,
                )
            )
            created += 1
    db.commit()
    return {"created": created}


# --------------------------------------------------------------------------- #
# Trip suggestions (dynamic) + accept (persist)
# --------------------------------------------------------------------------- #
@app.get("/persons/{person_id}/suggestions")
def get_suggestions(
    person_id: int,
    as_of: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    _get_person(db, person_id)
    ref = _parse_as_of(as_of)
    settings = db.get(Settings, person_id)

    # Use the Dubai (target) counter to determine pending + window.
    dubai = (
        db.query(CounterConfig)
        .filter(CounterConfig.person_id == person_id, CounterConfig.key == "dubai")
        .first()
    )
    if dubai is None:
        return {"pending": 0, "trips": []}

    from .counters import resolve_window

    win_start, win_end = resolve_window(dubai.window, ref)
    intervals = _coverage_intervals(db, person_id)
    per_date = engine.per_date_status(intervals, win_start, win_end)
    count = engine.count_country(per_date, dubai.country, win_start, win_end)
    pending = max(0, dubai.threshold - count)

    # Start suggesting after the last accepted trip, else from today.
    last_trip = (
        db.query(PlannedTrip)
        .filter(PlannedTrip.person_id == person_id)
        .order_by(PlannedTrip.to_date.desc())
        .first()
    )
    from datetime import timedelta

    start_from = ref
    if last_trip and last_trip.to_date >= ref:
        gap = settings.min_gap_days if settings else 14
        start_from = last_trip.to_date + timedelta(days=gap + 1)

    # Build planning constraints from commitment events (Feature 2). Only events
    # still ahead of us matter. Mandatory India events the user is attending are
    # hard blackout windows; travel-opportunity windows are preferred trip slots.
    events = (
        db.query(CommitmentEvent)
        .filter(CommitmentEvent.person_id == person_id)
        .filter(CommitmentEvent.to_date >= ref)
        .all()
    )
    blocked: List[Tuple[date, date, str]] = [
        (e.from_date, e.to_date, e.title or "commitment")
        for e in events
        if e.event_type == "mandatory" and e.country == "IN" and e.attend is True
    ]
    prefer: List[Tuple[date, date, str]] = [
        (e.from_date, e.to_date, e.title or "holidays")
        for e in events
        if e.event_type == "travel_opportunity" and e.attend is not False
    ]

    trips = suggest_trips(
        pending=pending,
        trip_len=settings.default_trip_len if settings else 18,
        min_gap_days=settings.min_gap_days if settings else 14,
        start_from=start_from,
        window_end=win_end,
        blocked=blocked,
        prefer=prefer,
    )
    return {"pending": pending, "trips": trips}


@app.get("/persons/{person_id}/trips", response_model=List[TripOut])
def list_trips(person_id: int, db: Session = Depends(get_db)):
    _get_person(db, person_id)
    return (
        db.query(PlannedTrip)
        .filter(PlannedTrip.person_id == person_id)
        .order_by(PlannedTrip.from_date)
        .all()
    )


@app.post("/persons/{person_id}/trips", response_model=TripOut, status_code=201)
def accept_trip(person_id: int, body: TripAcceptIn, db: Session = Depends(get_db)):
    _get_person(db, person_id)
    if body.to_date < body.from_date:
        raise HTTPException(status_code=400, detail="to_date must be >= from_date")
    trip = PlannedTrip(
        person_id=person_id,
        country=body.country,
        from_date=body.from_date,
        to_date=body.to_date,
        status="accepted",
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@app.delete("/trips/{trip_id}", status_code=204)
def delete_trip(trip_id: int, db: Session = Depends(get_db)):
    trip = db.get(PlannedTrip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    db.delete(trip)
    db.commit()


# --------------------------------------------------------------------------- #
# Commitment events (Feature 2) — manual CRUD + CSV import + RSVP
# --------------------------------------------------------------------------- #
@app.get("/persons/{person_id}/events", response_model=List[EventOut])
def list_events(person_id: int, db: Session = Depends(get_db)):
    _get_person(db, person_id)
    return (
        db.query(CommitmentEvent)
        .filter(CommitmentEvent.person_id == person_id)
        .order_by(CommitmentEvent.from_date)
        .all()
    )


@app.post("/persons/{person_id}/events", response_model=EventOut, status_code=201)
def create_event(person_id: int, body: EventIn, db: Session = Depends(get_db)):
    _get_person(db, person_id)
    event = CommitmentEvent(
        person_id=person_id,
        title=body.title,
        country=body.country,
        from_date=body.from_date,
        to_date=body.to_date,
        event_type=body.event_type,
        attend=body.attend,
        note=body.note,
        source="manual",
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@app.patch("/events/{event_id}", response_model=EventOut)
def update_event(event_id: int, body: EventUpdate, db: Session = Depends(get_db)):
    """Edit an event or answer its RSVP (send just `attend`)."""
    event = db.get(CommitmentEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    data = body.model_dump(exclude_unset=True)
    for field in ("title", "country", "from_date", "to_date", "event_type", "attend", "note"):
        if field in data:
            setattr(event, field, data[field])
    if event.to_date < event.from_date:
        raise HTTPException(status_code=400, detail="to_date must be >= from_date")
    db.commit()
    db.refresh(event)
    return event


@app.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(CommitmentEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(event)
    db.commit()


# Accept loose synonyms from the assistant's merged sheet.
_EVENT_TYPE_ALIASES = {
    "mandatory": "mandatory", "must": "mandatory", "required": "mandatory",
    "function": "mandatory", "wedding": "mandatory", "office": "mandatory",
    "optional": "optional", "maybe": "optional",
    "travel_opportunity": "travel_opportunity", "travel opportunity": "travel_opportunity",
    "holiday": "travel_opportunity", "holidays": "travel_opportunity",
    "vacation": "travel_opportunity", "opportunity": "travel_opportunity",
}
_COUNTRY_ALIASES = {
    "in": "IN", "india": "IN", "bombay": "IN", "mumbai": "IN", "🇮🇳": "IN",
    "ae": "AE", "uae": "AE", "dubai": "AE", "abu dhabi": "AE", "🇦🇪": "AE",
}


def _parse_bool(v: str) -> Optional[bool]:
    s = (v or "").strip().lower()
    if s in ("yes", "y", "true", "1", "attend", "attending"):
        return True
    if s in ("no", "n", "false", "0", "skip", "skipping"):
        return False
    return None


@app.post("/persons/{person_id}/events/import", status_code=201)
def import_events(
    person_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Import commitment events from a CSV (the assistant's merged iCal+Google sheet,
    exported to CSV). Flexible headers: title, country, from, to, type, attend, note."""
    _get_person(db, person_id)
    raw = file.file.read()
    try:
        text = raw.decode("utf-8-sig")  # tolerate Excel's BOM
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no header row")

    # Normalise headers -> lower-case keys.
    def norm(row: dict) -> dict:
        return {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}

    def pick(row: dict, *names: str) -> str:
        for n in names:
            if n in row and row[n]:
                return row[n]
        return ""

    created = 0
    errors: List[str] = []
    for i, raw_row in enumerate(reader, start=2):  # row 1 = header
        row = norm(raw_row)
        title = pick(row, "title", "event", "name", "summary")
        from_s = pick(row, "from", "from_date", "start", "start_date", "date")
        to_s = pick(row, "to", "to_date", "end", "end_date") or from_s
        if not from_s:
            errors.append(f"row {i}: missing start date")
            continue
        try:
            from_d = date.fromisoformat(from_s[:10])
            to_d = date.fromisoformat(to_s[:10])
        except ValueError:
            errors.append(f"row {i}: bad date (use YYYY-MM-DD)")
            continue
        if to_d < from_d:
            from_d, to_d = to_d, from_d
        country_raw = pick(row, "country", "location", "place").lower()
        country = _COUNTRY_ALIASES.get(country_raw, "IN")
        type_raw = pick(row, "type", "event_type", "category").lower()
        event_type = _EVENT_TYPE_ALIASES.get(type_raw, "mandatory")
        db.add(
            CommitmentEvent(
                person_id=person_id,
                title=title or "(untitled)",
                country=country,
                from_date=from_d,
                to_date=to_d,
                event_type=event_type,
                attend=_parse_bool(pick(row, "attend", "rsvp", "going")),
                note=pick(row, "note", "notes", "description"),
                source="csv",
            )
        )
        created += 1
    db.commit()
    return {"created": created, "errors": errors}


# --------------------------------------------------------------------------- #
# Counter config + settings
# --------------------------------------------------------------------------- #
@app.get("/persons/{person_id}/counters", response_model=List[CounterConfigOut])
def list_counters(person_id: int, db: Session = Depends(get_db)):
    _get_person(db, person_id)
    return (
        db.query(CounterConfig)
        .filter(CounterConfig.person_id == person_id)
        .order_by(CounterConfig.id)
        .all()
    )


@app.put("/persons/{person_id}/counters/{key}", response_model=CounterConfigOut)
def update_counter(
    person_id: int,
    key: str,
    body: CounterConfigIn,
    db: Session = Depends(get_db),
):
    _get_person(db, person_id)
    counter = (
        db.query(CounterConfig)
        .filter(CounterConfig.person_id == person_id, CounterConfig.key == key)
        .first()
    )
    if counter is None:
        raise HTTPException(status_code=404, detail="Counter not found")
    counter.label = body.label
    counter.country = body.country
    counter.mode = body.mode
    counter.threshold = body.threshold
    counter.window = body.window
    db.commit()
    db.refresh(counter)
    return counter


@app.get("/persons/{person_id}/settings", response_model=SettingsOut)
def get_settings(person_id: int, db: Session = Depends(get_db)):
    _get_person(db, person_id)
    settings = db.get(Settings, person_id)
    if settings is None:
        settings = Settings(person_id=person_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


@app.put("/persons/{person_id}/settings", response_model=SettingsOut)
def update_settings(person_id: int, body: SettingsIn, db: Session = Depends(get_db)):
    _get_person(db, person_id)
    settings = db.get(Settings, person_id)
    if settings is None:
        settings = Settings(person_id=person_id)
        db.add(settings)
    settings.default_trip_len = body.default_trip_len
    settings.min_gap_days = body.min_gap_days
    db.commit()
    db.refresh(settings)
    return settings
