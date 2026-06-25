"""Google Calendar sync — pure mapping (classify_event) + idempotent upsert."""
from __future__ import annotations

from datetime import date

from app import gcal

PID = 1  # seeded person


def _allday(eid, summary, start, end, **extra):
    return {"id": eid, "status": "confirmed", "summary": summary,
            "start": {"date": start}, "end": {"date": end}, **extra}


def _timed(eid, summary, start, end, **extra):
    return {"id": eid, "status": "confirmed", "summary": summary,
            "start": {"dateTime": start}, "end": {"dateTime": end}, **extra}


# --------------------------------------------------------------------------- #
# classify_event — pure
# --------------------------------------------------------------------------- #
def test_allday_country_event_is_presence_with_inclusive_end():
    # Google all-day end dates are EXCLUSIVE: 05 -> 19 means 5th..18th.
    cands = gcal.classify_event(_allday("e1", "India trip", "2026-01-05", "2026-01-19"))
    assert len(cands) == 1
    c = cands[0]
    assert c["kind"] == "presence"
    assert c["country"] == "IN"
    assert c["from_date"] == date(2026, 1, 5)
    assert c["to_date"] == date(2026, 1, 18)
    assert c["ext_id"] == "gcal:e1"


def test_single_allday_spans_one_day():
    cands = gcal.classify_event(_allday("e2", "Dubai", "2026-03-10", "2026-03-11"))
    assert cands[0]["kind"] == "presence"
    assert cands[0]["country"] == "AE"
    assert cands[0]["from_date"] == cands[0]["to_date"] == date(2026, 3, 10)


def test_allday_country_plus_keyword_yields_presence_and_commitment():
    cands = gcal.classify_event(
        _allday("e3", "Cousin's Wedding", "2026-02-01", "2026-02-04", location="Mumbai")
    )
    kinds = {c["kind"] for c in cands}
    assert kinds == {"presence", "commitment"}
    commit = next(c for c in cands if c["kind"] == "commitment")
    assert commit["event_type"] == "mandatory"
    assert commit["country"] == "IN"


def test_allday_no_country_is_optional_commitment():
    cands = gcal.classify_event(_allday("e4", "Some all-day note", "2026-05-01", "2026-05-02"))
    assert len(cands) == 1
    assert cands[0]["kind"] == "commitment"
    assert cands[0]["event_type"] == "optional"
    assert cands[0]["country"] == "OTHER"


def test_allday_holiday_keyword_is_travel_opportunity():
    cands = gcal.classify_event(_allday("e5", "Summer holidays", "2026-06-01", "2026-06-15"))
    assert cands[0]["event_type"] == "travel_opportunity"


def test_timed_meeting_without_keyword_is_skipped():
    cands = gcal.classify_event(
        _timed("e6", "Team sync", "2026-02-01T09:00:00+04:00", "2026-02-01T10:00:00+04:00")
    )
    assert cands == []


def test_timed_event_with_commitment_keyword_kept():
    cands = gcal.classify_event(
        _timed("e7", "Graduation ceremony", "2026-07-01T09:00:00+05:30", "2026-07-01T12:00:00+05:30")
    )
    assert len(cands) == 1
    assert cands[0]["kind"] == "commitment"
    assert cands[0]["event_type"] == "mandatory"


def test_cancelled_and_dateless_events_are_dropped():
    assert gcal.classify_event({"id": "x", "status": "cancelled", "summary": "India"}) == []
    assert gcal.classify_event({"id": "y", "status": "confirmed", "summary": "India"}) == []


# --------------------------------------------------------------------------- #
# /google/sync — idempotent upsert (no real network; events + token stubbed)
# --------------------------------------------------------------------------- #
def _link_google(refresh="r0"):
    """Insert a GoogleCredential with a non-expired access token so the sync
    endpoint never hits the network for a refresh."""
    from app.database import SessionLocal
    from app.models import GoogleCredential

    db = SessionLocal()
    try:
        db.query(GoogleCredential).filter(GoogleCredential.person_id == PID).delete()
        db.add(GoogleCredential(
            person_id=PID, email="t@example.com", refresh_token=refresh,
            access_token="valid", token_expiry="2999-01-01T00:00:00+00:00",
        ))
        db.commit()
    finally:
        db.close()


def test_sync_is_idempotent(client, monkeypatch):
    events = [
        _allday("trip1", "India trip", "2026-01-05", "2026-01-19"),
        _allday("wed1", "Wedding", "2026-02-01", "2026-02-03", location="Delhi"),
        _allday("hol1", "School holidays", "2026-06-01", "2026-06-10"),
        _timed("mtg1", "Standup", "2026-02-02T09:00:00+04:00", "2026-02-02T09:15:00+04:00"),
    ]
    monkeypatch.setattr(gcal, "fetch_events", lambda *a, **k: events)
    _link_google()

    first = client.post(f"/persons/{PID}/google/sync").json()
    assert first["scanned"] == 4
    assert first["skipped"] == 1                       # the standup meeting
    assert first["entries_created"] == 2               # India trip + wedding (in Delhi)
    assert first["events_created"] >= 2                # wedding commitment + holidays
    assert first["entries_updated"] == 0

    # Second identical sync creates nothing new — only updates.
    second = client.post(f"/persons/{PID}/google/sync").json()
    assert second["entries_created"] == 0
    assert second["events_created"] == 0
    assert second["entries_updated"] == first["entries_created"]

    # The presence rows actually landed and feed the entries list.
    entries = client.get(f"/persons/{PID}/entries").json()
    gcal_entries = [e for e in entries if e["source"] == "gcal"]
    assert len(gcal_entries) == 2
    india = next(e for e in gcal_entries if e["from_date"] == "2026-01-05")
    assert india["country"] == "IN" and india["to_date"] == "2026-01-18"


def test_sync_without_travel_skips_presence(client, monkeypatch):
    events = [_allday("trip2", "Dubai", "2026-04-01", "2026-04-08")]
    monkeypatch.setattr(gcal, "fetch_events", lambda *a, **k: events)
    _link_google()

    res = client.post(f"/persons/{PID}/google/sync?include_travel=false").json()
    assert res["entries_created"] == 0     # presence suppressed
    entries = client.get(f"/persons/{PID}/entries").json()
    assert [e for e in entries if e["source"] == "gcal"] == []


def test_status_and_disconnect(client):
    _link_google()
    st = client.get(f"/persons/{PID}/google/status").json()
    assert st["connected"] is True
    assert st["email"] == "t@example.com"

    client.delete(f"/persons/{PID}/google")
    st2 = client.get(f"/persons/{PID}/google/status").json()
    assert st2["connected"] is False
