"""Create tables and seed the 3 fixed profiles with default counters."""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import (
    COUNTRY_INDIA,
    COUNTRY_UAE,
    MODE_LIMIT,
    MODE_TARGET,
    WINDOW_CALENDAR,
    WINDOW_FINANCIAL,
    CounterConfig,
    Person,
    Settings,
)

PROFILES = [
    ("NKA", "NKA"),
    ("KKA", "KKA"),
    ("HKA", "HKA"),
]


def default_counters(person_id: int) -> list[CounterConfig]:
    return [
        CounterConfig(
            person_id=person_id,
            key="dubai",
            label="Dubai Days",
            country=COUNTRY_UAE,
            mode=MODE_TARGET,
            threshold=190,
            window=WINDOW_CALENDAR,
        ),
        CounterConfig(
            person_id=person_id,
            key="india",
            label="India Days",
            country=COUNTRY_INDIA,
            mode=MODE_LIMIT,
            threshold=175,
            window=WINDOW_FINANCIAL,
        ),
    ]


def seed(db: Session) -> None:
    if db.query(Person).count() > 0:
        return
    for code, name in PROFILES:
        p = Person(code=code, name=name)
        db.add(p)
        db.flush()  # assign p.id
        for c in default_counters(p.id):
            db.add(c)
        db.add(Settings(person_id=p.id))
    db.commit()


# Lightweight, idempotent column additions for tables that already exist in older
# DBs. `create_all` only creates MISSING tables — it never ALTERs existing ones —
# so new nullable columns are added here. (No Alembic in this project.)
_COLUMN_MIGRATIONS: dict[str, dict[str, str]] = {
    "manual_entries": {
        "dep_time": "VARCHAR(5)",
        "arr_time": "VARCHAR(5)",
        "ext_id": "VARCHAR(64)",
    },
    "commitment_events": {
        "ext_id": "VARCHAR(64)",
    },
}


def ensure_columns() -> None:
    """Add any missing nullable columns to existing tables (SQLite + Postgres)."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _COLUMN_MIGRATIONS.items():
            if table not in existing_tables:
                continue  # create_all will build it fresh with all columns
            present = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl_type in columns.items():
                if name not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl_type}"))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_columns()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized and seeded.")
