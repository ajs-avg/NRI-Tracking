# Deployment Guide — Vercel + Render + Supabase

Three pieces:

| Piece | Host | What runs |
|---|---|---|
| **Database** | Supabase | PostgreSQL |
| **Backend** | Render | FastAPI (`backend/`) |
| **Frontend** | Vercel | Next.js (`frontend/`) |

Deploy in this order: **Supabase → Render → Vercel** (each needs the previous one's URL).

---

## 1. Supabase (PostgreSQL)

1. Create a project at [supabase.com](https://supabase.com) → pick a region close to you → set a DB password.
2. **Project Settings → Database → Connection string → URI**. Copy it. It looks like:
   ```
   postgresql://postgres:[PASSWORD]@db.xxxx.supabase.co:5432/postgres
   ```
   - Replace `[PASSWORD]` with your DB password.
   - Append SSL: add `?sslmode=require` at the end.
   - (For serverless scale you can use the **Session pooler** URI on port `6543` instead — either works.)
3. Save this string — it's the `DATABASE_URL` for Render.

> Tables and the 3 profiles (NKA/KKA/HKA) are **created automatically** on first backend boot (`init_db()` runs `create_all` + seed). No manual SQL or migrations needed for this MVP.

---

## 2. Render (FastAPI backend)

1. Push this repo to GitHub. On [render.com](https://render.com): **New → Web Service** → connect the repo.
2. Settings:
   - **Root Directory:** `backend`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

   > **Python is pinned to 3.12** via `backend/.python-version` (+ `backend/runtime.txt`). Required: on Python 3.14 the pinned `pydantic-core==2.27.1` has no prebuilt wheel and tries to compile from Rust source, which fails on Render's read-only filesystem. If Render still picks a wrong version, also set env var `PYTHON_VERSION` = `3.12.8`.
3. **Environment variables:**
   | Key | Value |
   |---|---|
   | `DATABASE_URL` | the Supabase URI from step 1 |
   | `ANTHROPIC_API_KEY` | your Anthropic key (for ticket AI) — see below |
   | `ANTHROPIC_MODEL` | *(optional)* `claude-opus-4-8` (default) or `claude-haiku-4-5` for cheaper |
   | `GOOGLE_CLIENT_ID` | *(optional — Calendar sync)* from Google Cloud Console |
   | `GOOGLE_CLIENT_SECRET` | *(optional — Calendar sync)* from Google Cloud Console |
   | `GOOGLE_REDIRECT_URI` | *(Calendar sync)* `https://<your-render-url>/calendar/google/callback` |
   | `FRONTEND_BASE_URL` | *(Calendar sync)* your Vercel URL, e.g. `https://nri-tracker.vercel.app` |
4. Deploy. Note the service URL, e.g. `https://nri-tracker-api.onrender.com`. Open `/<url>/docs` to confirm it's up.

> CORS is already open (`allow_origins=["*"]`), so the Vercel frontend can call it. Lock this down to your Vercel domain later if you want.

---

## 3. Vercel (Next.js frontend)

1. On [vercel.com](https://vercel.com): **Add New → Project** → import the repo.
2. Settings:
   - **Root Directory:** `frontend`
   - Framework preset: **Next.js** (auto-detected)
3. **Environment variable:**
   | Key | Value |
   |---|---|
   | `NEXT_PUBLIC_API_BASE` | the Render URL from step 2, e.g. `https://nri-tracker-api.onrender.com` |
4. Deploy. Open the Vercel URL — dashboard should load NKA's data from the backend.

> `NEXT_PUBLIC_*` vars are baked in at build time. If you change the backend URL, **redeploy** the frontend.

---

## 4. Google Calendar sync (optional)

Lets each profile link a Google account so past & upcoming **trips** (all-day events
tagged with a country → travel days) and **commitments** (weddings/holidays/functions
→ planner constraints) are pulled in automatically. Skip this whole section if you
don't want calendar sync — the rest of the app works without it.

**One-time Google setup** (Google Cloud Console):
1. **console.cloud.google.com** → create a project → **APIs & Services → Library** →
   enable **Google Calendar API**.
2. **OAuth consent screen** → User type **External** → fill app name + your email →
   add scope **`.../auth/calendar.readonly`** → add the 3 users' Gmail addresses as
   **Test users** → keep the app in **Testing** (no Google verification needed for ≤100
   test users; users just click past an "unverified app" warning once).
3. **Credentials → Create Credentials → OAuth client ID → Web application.** Under
   **Authorized redirect URIs** add both:
   - `http://localhost:8000/calendar/google/callback` (local dev)
   - `https://<your-render-url>/calendar/google/callback` (production)
4. Copy the **Client ID** + **Client Secret** into the Render env vars above (and into
   `backend/.env` for local testing). Set `GOOGLE_REDIRECT_URI` to the matching callback
   URL and `FRONTEND_BASE_URL` to your Vercel URL.

**Use it:** open the app → **Settings → Google Calendar → Connect Google Calendar** →
allow access → **Sync now**. Re-syncing is idempotent (matched by Google event id, so no
duplicates). Imported rows carry `source = "gcal"` and can be edited/deleted on the
Entries and Commitments pages like any other.

> Mapping policy: an **all-day** event whose title/location names a country (India/Dubai/
> etc.) becomes a travel **day-range** that feeds the counters; weddings, holidays,
> functions, exams, etc. become **commitments**; ordinary timed meetings are ignored.

---

## Quick checklist
- [ ] Supabase project created, `DATABASE_URL` copied (with `?sslmode=require`)
- [ ] Render service: root `backend`, env `DATABASE_URL` + `ANTHROPIC_API_KEY`, `/docs` reachable
- [ ] Vercel project: root `frontend`, env `NEXT_PUBLIC_API_BASE` = Render URL
- [ ] Open Vercel URL → profiles + dashboard load → upload a ticket to test AI

## Notes
- **Render free tier sleeps** after inactivity; first request after idle is slow (cold start). Data is safe in Supabase regardless.
- **Ticket images are not stored** — they're sent to Claude for extraction and discarded; only the extracted day-entries are saved.
- Costs: Supabase + Render + Vercel all have free tiers sufficient for 3 users. Anthropic API is pay-per-use (only when analysing tickets).
