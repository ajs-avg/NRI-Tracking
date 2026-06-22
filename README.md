# NRI Residency Tracker (Web App — Phase 1)

Track how many days **NKA / KKA / HKA** spend in **India** vs **Dubai/UAE** to
manage NRI residency. **Manual entry only** for now (GPS comes later); the
architecture keeps GPS pluggable without changing the counting logic.

- **Backend:** FastAPI + SQLAlchemy + SQLite
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind + shadcn-style UI
- **Counting engine** is the single source of truth — dashboard, calendar,
  suggestions and allowance all derive from it.

## Core rule

A date is credited to **every** country whose entry range covers it. Range
endpoints are **inclusive**, so two ranges sharing a boundary date make that day
a **travel day** (both countries +1). Uncovered past days are **UNKNOWN** (`?`).

- **Dubai (UAE)** counter → `target_to_reach`, threshold 190, **calendar year** (Jan–Dec).
- **India** counter → `limit_to_watch`, threshold 175, **financial year** (Apr–Mar).
- **Allowance** = `(days left in target window) − (Dubai days still pending)`.

Counters are configurable per profile (mode / threshold / window) in Settings.

## Run

### 1. Backend (port 8000)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
Tables are created and the 3 profiles seeded automatically on first start.
SQLite file: `backend/nri_tracker.db`.

### 2. Frontend (port 3000)
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:3000. API base is set in `frontend/.env.local`
(`NEXT_PUBLIC_API_BASE=http://localhost:8000`).

### Tests
```bash
cd backend && source .venv/bin/activate && pytest -q
```

## API summary
| Method | Path | Purpose |
|---|---|---|
| GET | `/persons` | List NKA/KKA/HKA |
| GET | `/persons/{id}/summary?as_of=YYYY-MM-DD` | Dashboard counters + travel/unknown |
| GET | `/persons/{id}/calendar?month=YYYY-MM` | Per-date status (india/uae/both/unknown/future) |
| GET/POST | `/persons/{id}/entries` | List / add manual range entry |
| DELETE | `/entries/{id}` | Delete entry |
| GET | `/persons/{id}/suggestions` | Dynamic Dubai trip schedule (not persisted) |
| GET/POST | `/persons/{id}/trips` | List / accept (persist) a trip |
| DELETE | `/trips/{id}` | Remove accepted trip |
| GET/PUT | `/persons/{id}/counters/{key}` | Read / edit counter config |
| GET/PUT | `/persons/{id}/settings` | Trip length & gap |

## Notes / future
- UI components are hand-rolled in the shadcn style (Card/Button/Progress) to keep
  the dependency footprint small; swap for the shadcn CLI later if desired.
- **GPS phase:** add a `LocationPing` source that feeds `engine.Interval`s through
  `_coverage_intervals()` in `backend/app/main.py` — the engine and all counters
  stay unchanged.
