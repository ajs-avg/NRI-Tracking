"""Google Calendar sync — OAuth + event fetch + mapping to our domain.

No heavy Google SDK: we speak OAuth 2.0 and the Calendar v3 REST API directly
over httpx (same philosophy as tickets.py — works everywhere incl. Render).

Flow
----
1. Frontend opens ``build_auth_url(person_id)`` — Google asks the user to allow
   read-only Calendar access.
2. Google redirects back to ``GOOGLE_REDIRECT_URI`` with a ``code``; we call
   ``exchange_code`` to get an access token + a long-lived **refresh token**
   (stored per person in ``GoogleCredential``).
3. On each sync we ``ensure_access_token`` (refreshing if expired) and
   ``fetch_events`` for a date window, then ``classify_event`` maps each raw
   Google event into our domain:
     - an all-day event tagged with a known country (IN/AE) -> a PRESENCE row
       (ManualEntry) — this is "where the person was", which feeds counting;
     - an all-day event, or a keyword-matching timed event -> a COMMITMENT row
       (CommitmentEvent) — a planning constraint, never counted;
     - an ordinary timed meeting with no signal -> skipped.

``classify_event`` is a PURE function (no I/O) so it is unit-tested directly.

Env:
  GOOGLE_CLIENT_ID
  GOOGLE_CLIENT_SECRET
  GOOGLE_REDIRECT_URI   e.g. https://<render>/calendar/google/callback
  FRONTEND_BASE_URL     where the callback sends the user back (e.g. Vercel URL)
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import httpx

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"  # noqa: S105 - public URL
USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"
EVENTS_ENDPOINT = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

# Read-only Calendar + the user's email (so we can show which account is linked).
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

# Keyword -> our country code. Mirrors main.py's _COUNTRY_ALIASES so the Google
# path classifies the same way the CSV import does.
_COUNTRY_KEYWORDS: Dict[str, str] = {
    "india": "IN", "indian": "IN", "bharat": "IN", "mumbai": "IN", "bombay": "IN",
    "delhi": "IN", "bengaluru": "IN", "bangalore": "IN", "chennai": "IN",
    "hyderabad": "IN", "kolkata": "IN", "pune": "IN", "🇮🇳": "IN",
    "uae": "AE", "u.a.e": "AE", "emirates": "AE", "dubai": "AE", "abu dhabi": "AE",
    "abudhabi": "AE", "sharjah": "AE", "🇦🇪": "AE",
}

# Keyword -> commitment event_type. Mirrors main.py's _EVENT_TYPE_ALIASES.
# Deliberately NOT including generic work words ("meeting", "office", "call") so
# ordinary timed meetings stay noise and are skipped — only travel-relevant
# commitments are pulled in.
_TYPE_KEYWORDS: Dict[str, str] = {
    "wedding": "mandatory", "shaadi": "mandatory", "marriage": "mandatory",
    "function": "mandatory", "ceremony": "mandatory", "exam": "mandatory",
    "graduation": "mandatory", "anniversary": "mandatory",
    "holiday": "travel_opportunity", "holidays": "travel_opportunity",
    "vacation": "travel_opportunity", "break": "travel_opportunity",
    "diwali": "travel_opportunity", "eid": "travel_opportunity",
    "festival": "travel_opportunity", "puja": "travel_opportunity",
}


class GoogleCalendarError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def _cfg(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise GoogleCalendarError(
            f"{name} is not set — configure Google OAuth env vars to use Calendar sync."
        )
    return val


def is_configured() -> bool:
    return all(
        os.environ.get(k, "").strip()
        for k in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI")
    )


def frontend_base() -> str:
    return os.environ.get("FRONTEND_BASE_URL", "").strip().rstrip("/")


# --------------------------------------------------------------------------- #
# OAuth
# --------------------------------------------------------------------------- #
def build_auth_url(person_id: int) -> str:
    """Build the Google consent URL. ``state`` carries the person id back to us."""
    from urllib.parse import urlencode

    params = {
        "client_id": _cfg("GOOGLE_CLIENT_ID"),
        "redirect_uri": _cfg("GOOGLE_REDIRECT_URI"),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",   # we want a refresh token
        "prompt": "consent",        # force a refresh token every time
        "include_granted_scopes": "true",
        "state": str(person_id),
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


def exchange_code(code: str) -> Dict:
    """Swap an auth code for tokens. Returns the raw Google token response."""
    resp = httpx.post(
        TOKEN_ENDPOINT,
        data={
            "code": code,
            "client_id": _cfg("GOOGLE_CLIENT_ID"),
            "client_secret": _cfg("GOOGLE_CLIENT_SECRET"),
            "redirect_uri": _cfg("GOOGLE_REDIRECT_URI"),
            "grant_type": "authorization_code",
        },
        timeout=30.0,
    )
    if resp.status_code != 200:
        raise GoogleCalendarError(f"Token exchange failed {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def refresh_access_token(refresh_token: str) -> Dict:
    resp = httpx.post(
        TOKEN_ENDPOINT,
        data={
            "refresh_token": refresh_token,
            "client_id": _cfg("GOOGLE_CLIENT_ID"),
            "client_secret": _cfg("GOOGLE_CLIENT_SECRET"),
            "grant_type": "refresh_token",
        },
        timeout=30.0,
    )
    if resp.status_code != 200:
        raise GoogleCalendarError(f"Token refresh failed {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def fetch_email(access_token: str) -> str:
    try:
        resp = httpx.get(
            USERINFO_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        )
        if resp.status_code == 200:
            return resp.json().get("email", "") or ""
    except httpx.HTTPError:
        pass
    return ""


def expiry_from_response(token: Dict) -> str:
    """ISO timestamp when the access token expires (default 1h), minus a 60s buffer."""
    seconds = int(token.get("expires_in", 3600))
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds - 60)).isoformat()


def is_expired(expiry_iso: Optional[str]) -> bool:
    if not expiry_iso:
        return True
    try:
        return datetime.now(timezone.utc) >= datetime.fromisoformat(expiry_iso)
    except ValueError:
        return True


# --------------------------------------------------------------------------- #
# Calendar events
# --------------------------------------------------------------------------- #
def fetch_events(access_token: str, time_min: date, time_max: date) -> List[Dict]:
    """All events in [time_min, time_max), recurrences expanded, paginated."""
    out: List[Dict] = []
    page_token: Optional[str] = None
    params = {
        "timeMin": datetime.combine(time_min, datetime.min.time(), timezone.utc).isoformat(),
        "timeMax": datetime.combine(time_max, datetime.min.time(), timezone.utc).isoformat(),
        "singleEvents": "true",       # expand recurring events into instances
        "orderBy": "startTime",
        "maxResults": "250",
        "showDeleted": "false",
    }
    for _ in range(40):  # hard page cap (40 * 250 = 10k events) — safety net
        q = dict(params)
        if page_token:
            q["pageToken"] = page_token
        resp = httpx.get(
            EVENTS_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
            params=q,
            timeout=60.0,
        )
        if resp.status_code != 200:
            raise GoogleCalendarError(f"Calendar API {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        out.extend(data.get("items", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return out


# --------------------------------------------------------------------------- #
# Mapping (pure) — Google event -> our domain rows
# --------------------------------------------------------------------------- #
def _detect_country(text: str) -> Optional[str]:
    t = (text or "").lower()
    for kw, code in _COUNTRY_KEYWORDS.items():
        if kw in t:
            return code
    return None


def _detect_type(text: str) -> Optional[str]:
    t = (text or "").lower()
    for kw, etype in _TYPE_KEYWORDS.items():
        if kw in t:
            return etype
    return None


def _parse_endpoint(node: Dict) -> Tuple[Optional[date], bool]:
    """Return (date, is_all_day) for a Google event start/end node."""
    if not node:
        return None, False
    if node.get("date"):  # all-day event: "YYYY-MM-DD"
        try:
            return date.fromisoformat(node["date"][:10]), True
        except ValueError:
            return None, True
    if node.get("dateTime"):  # timed event: full RFC-3339 timestamp
        try:
            return date.fromisoformat(node["dateTime"][:10]), False
        except ValueError:
            return None, False
    return None, False


def classify_event(event: Dict) -> List[Dict]:
    """Map one raw Google event to 0..2 candidate rows.

    Each candidate is a dict with ``kind`` = "presence" | "commitment" plus the
    fields needed to build a ManualEntry / CommitmentEvent. ``ext_id`` ties the
    row back to the Google event so re-syncing updates instead of duplicating.

    Policy (see module docstring):
      - all-day + known country  -> presence (+ commitment if a keyword matches)
      - all-day, no/other country -> commitment (optional unless keyword matches)
      - timed + commitment keyword -> commitment
      - timed, no keyword          -> skipped (ordinary meeting)
    """
    if event.get("status") == "cancelled":
        return []
    title = (event.get("summary") or "").strip()
    location = (event.get("location") or "").strip()
    description = (event.get("description") or "").strip()
    blob = f"{title} {location} {description}"

    start_d, all_day = _parse_endpoint(event.get("start", {}))
    end_d, _ = _parse_endpoint(event.get("end", {}))
    if start_d is None:
        return []
    if end_d is None:
        end_d = start_d
    # Google all-day end dates are EXCLUSIVE — subtract a day so a single all-day
    # event spans exactly one date, and a 5th–7th trip ends on the 7th.
    if all_day and end_d > start_d:
        end_d = end_d - timedelta(days=1)
    if end_d < start_d:
        end_d = start_d

    ext_id = f"gcal:{event.get('id', '')}"
    country = _detect_country(blob)
    etype = _detect_type(blob)
    title = title or "(untitled)"
    candidates: List[Dict] = []

    if all_day and country in ("IN", "AE"):
        candidates.append(
            {
                "kind": "presence",
                "ext_id": ext_id,
                "country": country,
                "from_date": start_d,
                "to_date": end_d,
                "note": title,
            }
        )
        # A country trip that is also a wedding/holiday is worth keeping as a
        # planner constraint too — but only when a keyword actually matched.
        if etype is not None:
            candidates.append(
                {
                    "kind": "commitment",
                    "ext_id": ext_id,
                    "title": title,
                    "country": country,
                    "from_date": start_d,
                    "to_date": end_d,
                    "event_type": etype,
                }
            )
    elif all_day:
        candidates.append(
            {
                "kind": "commitment",
                "ext_id": ext_id,
                "title": title,
                "country": country or "OTHER",
                "from_date": start_d,
                "to_date": end_d,
                "event_type": etype or "optional",
            }
        )
    elif etype is not None:  # timed, but clearly a commitment by keyword
        candidates.append(
            {
                "kind": "commitment",
                "ext_id": ext_id,
                "title": title,
                "country": country or "OTHER",
                "from_date": start_d,
                "to_date": end_d,
                "event_type": etype,
            }
        )
    # else: ordinary timed meeting -> skip
    return candidates
