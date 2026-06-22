"""Create tables and seed the 3 fixed profiles with default counters."""
from __future__ import annotations

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


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized and seeded.")
