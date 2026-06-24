"""Test fixtures — isolated temp SQLite DB + clean state per test."""
from __future__ import annotations

import os
import tempfile

# Point the app at a throwaway SQLite file BEFORE app modules import the engine.
_DB = os.path.join(tempfile.mkdtemp(prefix="nri_test_"), "nri_test.db")
os.environ["NRI_DB_PATH"] = _DB
os.environ.pop("DATABASE_URL", None)

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _clean():
    """Ensure schema exists and wipe per-person data between tests (persons persist)."""
    from app.seed import init_db
    from app.database import SessionLocal
    from app.models import CommitmentEvent, ManualEntry, PlannedTrip

    init_db()
    db = SessionLocal()
    try:
        for model in (ManualEntry, CommitmentEvent, PlannedTrip):
            db.query(model).delete()
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c
