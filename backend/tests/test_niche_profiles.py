"""
NICHE PROFILE TESTS (Phase 1)

Covers:
  1. every seeded id returns a NicheProfile with every schema field populated
     and correctly typed
  2. an unknown id raises NicheProfileNotFound with the bad id in the message
  3. the accessor never returns a partial object — a malformed row raises
     NicheProfileInvalid instead of coming back with missing pieces

Runs against the same DB the rest of the suite uses (SQLite by default, or
TEST_DATABASE_URL). Profiles are seeded from app/niches/profiles.json, so the
data file is under test too.
"""
import json

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.models import NicheProfileRow
from app.niches import (
    AspectRatio,
    HookStyle,
    NicheProfile,
    NicheProfileInvalid,
    NicheProfileNotFound,
    Pacing,
    get_niche_profile,
    list_niche_profiles,
)
from app.niches.schema import NICHE_PROFILE_FIELDS
from app.niches.seed import PROFILES_PATH, load_profiles_file, seed_niche_profiles

# The six ids Appendix A defines. If profiles.json drifts, this test fails on purpose.
SEEDED_IDS = [
    "true_crime_narration",
    "whatif_hypothetical",
    "tech_explainer",
    "motivational",
    "documentary",
    "listicle",
]

# Field -> the type a pipeline stage may rely on.
EXPECTED_TYPES = {
    "id": str,
    "display_name": str,
    "script_system_prompt": str,
    "hook_style": HookStyle,
    "pacing": Pacing,
    "visual_prompt_modifiers": str,
    "voice_tone": str,
    "music_mood": str,
    "caption_style": str,
    "aspect_default": AspectRatio,
    "needs_tts": bool,
}


@pytest.fixture(scope="module", autouse=True)
def seeded(db_session_module):
    seed_niche_profiles(db_session_module)
    yield


@pytest.fixture(scope="module")
def db_session_module():
    # conftest points DATABASE_URL at the test DB before the app is imported,
    # so the app's own session factory is already bound to it.
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# (1) every seeded id -> complete, correctly typed object
# ---------------------------------------------------------------------------

def test_schema_field_list_matches_appendix_a():
    assert set(NICHE_PROFILE_FIELDS) == set(EXPECTED_TYPES), "schema drifted from Appendix A"


def test_profiles_file_contains_exactly_the_six_planned_ids():
    ids = [p.id for p in load_profiles_file()]
    assert ids == SEEDED_IDS


@pytest.mark.parametrize("niche_id", SEEDED_IDS)
def test_get_seeded_profile_is_complete_and_typed(niche_id, db_session: Session):
    profile = get_niche_profile(niche_id, db_session)

    assert isinstance(profile, NicheProfile)
    assert profile.id == niche_id

    for field, expected_type in EXPECTED_TYPES.items():
        assert hasattr(profile, field), f"{niche_id}: missing field {field}"
        value = getattr(profile, field)
        assert value is not None, f"{niche_id}: {field} is None"
        assert isinstance(value, expected_type), (
            f"{niche_id}: {field} is {type(value).__name__}, expected {expected_type.__name__}"
        )
        if expected_type is str:
            assert value.strip(), f"{niche_id}: {field} is blank"

    # nested pacing object is itself complete and typed
    assert isinstance(profile.pacing.avg_clip_seconds, (int, float))
    assert profile.pacing.avg_clip_seconds > 0
    assert isinstance(profile.pacing.cuts_style, str) and profile.pacing.cuts_style

    # bool must be a real bool, not a truthy int/str from the DB
    assert type(profile.needs_tts) is bool


@pytest.mark.parametrize("niche_id", SEEDED_IDS)
def test_seeded_profile_matches_data_file_verbatim(niche_id, db_session: Session):
    """What comes back from the DB is exactly what Appendix A / profiles.json says."""
    from_file = {p.id: p for p in load_profiles_file()}[niche_id]
    from_db = get_niche_profile(niche_id, db_session)
    assert from_db == from_file


def test_two_worked_examples_are_final_and_four_stubs_are_placeholders(db_session: Session):
    """Appendix A ships two finished profiles; the other four still carry PLACEHOLDER
    prompt text that must get a human writing pass before launch."""
    final = {"true_crime_narration", "whatif_hypothetical"}
    for niche_id in SEEDED_IDS:
        profile = get_niche_profile(niche_id, db_session)
        assert profile.is_placeholder == (niche_id not in final), niche_id


def test_list_returns_all_seeded_profiles(db_session: Session):
    listed = {p.id: p for p in list_niche_profiles(db_session)}
    assert set(SEEDED_IDS) <= set(listed)
    for p in listed.values():
        assert isinstance(p, NicheProfile)


def test_profile_is_immutable(db_session: Session):
    """Stages read style off the profile; none of them may mutate it."""
    profile = get_niche_profile("true_crime_narration", db_session)
    with pytest.raises(Exception):
        profile.needs_tts = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# (2) unknown id -> specific error naming the id
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_id", ["does_not_exist", "true_crime", "TRUE_CRIME_NARRATION", ""])
def test_unknown_id_raises_not_found_with_id_in_message(bad_id, db_session: Session):
    with pytest.raises(NicheProfileNotFound) as excinfo:
        get_niche_profile(bad_id, db_session)
    assert excinfo.value.niche_id == bad_id
    assert repr(bad_id) in str(excinfo.value)
    assert "not found" in str(excinfo.value).lower()


def test_unknown_id_never_returns_none_or_default(db_session: Session):
    """Belt and braces: the call must raise, not fall through to any value."""
    raised = False
    result = "sentinel"
    try:
        result = get_niche_profile("nope_nope_nope", db_session)
    except NicheProfileNotFound:
        raised = True
    assert raised
    assert result == "sentinel"


# ---------------------------------------------------------------------------
# (3) never a partial object
# ---------------------------------------------------------------------------

def _insert_raw_row(db: Session, **overrides):
    """Insert a row that bypasses the accessor, so we can corrupt it deliberately."""
    base = json.loads(PROFILES_PATH.read_text())[0]
    base["id"] = "corrupt_test_profile"
    base.update(overrides)
    db.add(NicheProfileRow(**base))
    db.flush()


@pytest.mark.parametrize("corruption", [
    {"pacing": {"avg_clip_seconds": 6}},                 # nested field missing
    {"pacing": {"avg_clip_seconds": 6, "cuts_style": ""}},  # nested field blank
    {"pacing": {"avg_clip_seconds": 0, "cuts_style": "x"}},  # nested field out of range
    {"hook_style": "not_a_real_hook"},                    # enum violated
    {"aspect_default": "4:3"},                            # enum violated
    {"voice_tone": ""},                                   # blank required string
])
def test_malformed_row_raises_invalid_instead_of_partial_object(corruption, db_session: Session):
    """Two layers defend against partial objects: Postgres check constraints may
    refuse the row outright (IntegrityError), and if a bad row does get stored
    (SQLite has no such constraints) the accessor must raise, not return it."""
    db_session.begin_nested()
    try:
        try:
            _insert_raw_row(db_session, **corruption)
        except IntegrityError:
            return  # the database refused to store it — nothing partial can ever be read
        with pytest.raises(NicheProfileInvalid) as excinfo:
            get_niche_profile("corrupt_test_profile", db_session)
        assert excinfo.value.niche_id == "corrupt_test_profile"
        assert "corrupt_test_profile" in str(excinfo.value)
    finally:
        db_session.rollback()


def test_accessor_output_has_no_extra_or_missing_keys(db_session: Session):
    profile = get_niche_profile("whatif_hypothetical", db_session)
    dumped = profile.model_dump()
    assert set(dumped) == set(NICHE_PROFILE_FIELDS)
    assert set(dumped["pacing"]) == {"avg_clip_seconds", "cuts_style"}
