"""Feature 1 (entry edit) + Feature 2 (events, CSV import, constraint-aware planner)."""
from __future__ import annotations

from datetime import date

from app.suggestions import suggest_trips

PID = 1  # seeded person


def _d(s: str) -> date:
    return date.fromisoformat(s)


# --------------------------------------------------------------------------- #
# Planner — pure function (blocked + prefer)
# --------------------------------------------------------------------------- #
def test_planner_blocks_mandatory_window():
    # A commitment 1-31 Aug must never be covered by a UAE trip.
    blocked = [(_d("2026-08-01"), _d("2026-08-31"), "Wedding")]
    trips = suggest_trips(
        pending=60,
        trip_len=18,
        min_gap_days=14,
        start_from=_d("2026-07-20"),
        window_end=_d("2026-12-31"),
        blocked=blocked,
    )
    for t in trips:
        # No trip day may fall inside the blocked window.
        assert not (t["from"] <= "2026-08-31" and t["to"] >= "2026-08-01"), t
    # The first trip should be clipped to end before the commitment starts.
    assert trips[0]["to"] < "2026-08-01"
    # A later trip should resume after the commitment (carries the "after" note).
    assert any(t["from"] > "2026-08-31" for t in trips)
    assert any("Wedding" in t["note"] for t in trips)


def test_planner_prefers_travel_window():
    # Pending small; a holiday window starts soon -> the trip should snap into it.
    prefer = [(_d("2026-07-10"), _d("2026-07-25"), "Summer break")]
    trips = suggest_trips(
        pending=10,
        trip_len=18,
        min_gap_days=14,
        start_from=_d("2026-07-01"),
        window_end=_d("2026-12-31"),
        prefer=prefer,
    )
    assert trips
    assert trips[0]["from"] == "2026-07-10"
    assert "Summer break" in trips[0]["note"]


def test_planner_unconstrained_matches_legacy():
    # With no events, behaviour is unchanged from before.
    trips = suggest_trips(
        pending=90, trip_len=18, min_gap_days=14,
        start_from=_d("2026-06-22"), window_end=_d("2026-12-31"),
    )
    assert [t["pendingAfter"] for t in trips] == [72, 54, 36, 18, 0]


# --------------------------------------------------------------------------- #
# Feature 1 — editing an entry re-computes counts
# --------------------------------------------------------------------------- #
def test_entry_edit_shifts_count_across_year_boundary(client):
    # AE day on 31 Dec 2026 counts for the 2026 Dubai (calendar-year) target.
    r = client.post(
        f"/persons/{PID}/entries",
        json={"country": "AE", "from_date": "2026-12-31", "to_date": "2026-12-31", "arr_time": "23:30"},
    )
    assert r.status_code == 201, r.text
    entry_id = r.json()["id"]
    assert r.json()["arr_time"] == "23:30"

    def dubai_count():
        s = client.get(f"/persons/{PID}/summary?as_of=2026-12-31").json()
        return next(c["count"] for c in s["counters"] if c["key"] == "dubai")

    assert dubai_count() == 1

    # Immigration actually next day -> move the entry to 1 Jan 2027 (now outside 2026).
    r = client.patch(f"/entries/{entry_id}", json={"from_date": "2027-01-01", "to_date": "2027-01-01"})
    assert r.status_code == 200, r.text
    assert dubai_count() == 0


def test_entry_patch_rejects_reversed_range(client):
    r = client.post(
        f"/persons/{PID}/entries",
        json={"country": "AE", "from_date": "2026-05-01", "to_date": "2026-05-05"},
    )
    eid = r.json()["id"]
    r = client.patch(f"/entries/{eid}", json={"to_date": "2026-04-01"})
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Feature 2 — CSV import + RSVP-driven blocking via the suggestions endpoint
# --------------------------------------------------------------------------- #
def test_csv_import_creates_events(client):
    csv = (
        "title,country,from,to,type,attend,note\n"
        "School annual day,India,2026-09-15,2026-09-15,mandatory,yes,bring camera\n"
        "Winter vacation,Bombay,2026-12-20,2027-01-05,holidays,,\n"
    )
    r = client.post(
        f"/persons/{PID}/events/import",
        files={"file": ("events.csv", csv, "text/csv")},
    )
    assert r.status_code == 201, r.text
    assert r.json()["created"] == 2

    events = client.get(f"/persons/{PID}/events").json()
    by_title = {e["title"]: e for e in events}
    assert by_title["School annual day"]["event_type"] == "mandatory"
    assert by_title["School annual day"]["country"] == "IN"
    assert by_title["School annual day"]["attend"] is True
    assert by_title["Winter vacation"]["event_type"] == "travel_opportunity"
    assert by_title["Winter vacation"]["country"] == "IN"


def test_suggestions_route_around_attending_mandatory_event(client):
    # Create a mandatory India event the user is attending, in the suggestion path.
    client.post(
        f"/persons/{PID}/events",
        json={
            "title": "Daughter's recital",
            "country": "IN",
            "from_date": "2026-08-01",
            "to_date": "2026-08-20",
            "event_type": "mandatory",
            "attend": True,
        },
    )
    data = client.get(f"/persons/{PID}/suggestions?as_of=2026-07-15").json()
    assert data["trips"], data
    for t in data["trips"]:
        assert not (t["from"] <= "2026-08-20" and t["to"] >= "2026-08-01"), t


def test_skipped_event_does_not_block(client):
    # Same event but skipped -> it must NOT constrain the planner.
    client.post(
        f"/persons/{PID}/events",
        json={
            "title": "Optional meet",
            "country": "IN",
            "from_date": "2026-08-01",
            "to_date": "2026-08-20",
            "event_type": "mandatory",
            "attend": False,
        },
    )
    data = client.get(f"/persons/{PID}/suggestions?as_of=2026-07-15").json()
    # A trip is allowed to overlap because the user is skipping it.
    assert any(t["from"] <= "2026-08-20" and t["to"] >= "2026-08-01" for t in data["trips"])
