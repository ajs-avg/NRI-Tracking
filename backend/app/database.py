"""SQLite + SQLAlchemy setup."""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Prefer a hosted Postgres (e.g. Supabase) via DATABASE_URL; fall back to local
# SQLite for development. Supabase/Heroku-style "postgres://" URLs are normalised
# to the "postgresql://" scheme SQLAlchemy expects.
_raw_url = os.environ.get("DATABASE_URL", "").strip()
if _raw_url:
    if _raw_url.startswith("postgres://"):
        _raw_url = _raw_url.replace("postgres://", "postgresql://", 1)
    DATABASE_URL = _raw_url
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    DB_PATH = os.environ.get("NRI_DB_PATH", os.path.join(BASE_DIR, "nri_tracker.db"))
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
