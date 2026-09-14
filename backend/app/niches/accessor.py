"""
Typed accessor for niche profiles. The only sanctioned way to read them.

    from app.niches import get_niche_profile
    profile = get_niche_profile("true_crime_narration", db)

Raises NicheProfileNotFound for an unknown id and NicheProfileInvalid if the
stored row fails schema validation. Never returns None, never returns a
default profile, never returns a partial object.
"""

from __future__ import annotations

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.models import NicheProfileRow
from app.niches.schema import (
    NICHE_PROFILE_FIELDS,
    NicheProfile,
    NicheProfileInvalid,
    NicheProfileNotFound,
)


def _row_to_profile(row: NicheProfileRow) -> NicheProfile:
    data = {name: getattr(row, name) for name in NICHE_PROFILE_FIELDS}
    try:
        return NicheProfile.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}" for e in exc.errors()
        )
        raise NicheProfileInvalid(row.id, problems) from exc


def get_niche_profile(niche_id: str, db: Session) -> NicheProfile:
    """Return the full, validated NicheProfile for `niche_id`, or raise."""
    if not isinstance(niche_id, str) or not niche_id:
        raise NicheProfileNotFound(str(niche_id))
    row = db.get(NicheProfileRow, niche_id)
    if row is None:
        raise NicheProfileNotFound(niche_id)
    return _row_to_profile(row)


def list_niche_profiles(db: Session) -> list[NicheProfile]:
    """All profiles, validated, ordered by display name. Raises on the first invalid row."""
    rows = db.query(NicheProfileRow).order_by(NicheProfileRow.display_name).all()
    return [_row_to_profile(r) for r in rows]
