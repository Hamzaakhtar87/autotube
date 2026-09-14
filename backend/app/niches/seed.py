"""
Seed / upsert niche profiles from profiles.json into the niche_profiles table.

    cd backend && python -m app.niches.seed          # uses DATABASE_URL

Idempotent: existing ids are updated to match the file, new ids inserted,
ids not in the file are left alone (the DB may hold profiles added later).
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.models import NicheProfileRow
from app.niches.schema import NICHE_PROFILE_FIELDS, NicheProfile

PROFILES_PATH = Path(__file__).with_name("profiles.json")


def load_profiles_file(path: Path = PROFILES_PATH) -> list[NicheProfile]:
    """Parse and validate the data file. Fails loudly if any entry is malformed."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{path} must contain a non-empty JSON array of profiles")
    profiles = [NicheProfile.model_validate(item) for item in raw]
    ids = [p.id for p in profiles]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate profile ids in {path}: {sorted(i for i in ids if ids.count(i) > 1)}")
    return profiles


def seed_niche_profiles(db: Session, path: Path = PROFILES_PATH) -> list[str]:
    """Upsert every profile in the file. Returns the ids written."""
    written: list[str] = []
    for profile in load_profiles_file(path):
        values = profile.model_dump(mode="json")  # enums -> str, Pacing -> dict
        row = db.get(NicheProfileRow, profile.id)
        if row is None:
            row = NicheProfileRow(**values)
            db.add(row)
        else:
            for name in NICHE_PROFILE_FIELDS:
                setattr(row, name, values[name])
        written.append(profile.id)
    db.commit()
    return written


if __name__ == "__main__":
    from app.db import SessionLocal

    session = SessionLocal()
    try:
        ids = seed_niche_profiles(session)
        print(f"Seeded {len(ids)} niche profiles: {', '.join(ids)}")
    finally:
        session.close()
