"""
Niche profile schema — the single source of truth for a niche's style.

Every pipeline stage (script, visuals, voice, music, captions, assembly) reads
its style settings off a NicheProfile. No stage may branch on the niche id;
if you find yourself writing `if niche == "..."`, add a field here instead.

Field list mirrors Appendix A of AUTOTUBE_CLAUDE_CODE_PLAN.md exactly. Every
field is required — there are no optionals for stages to null-check.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, ConfigDict, Field


class HookStyle(str, enum.Enum):
    """The opening pattern the script must follow."""
    COLD_OPEN_QUESTION = "cold_open_question"
    DIRECT_QUESTION_PATTERN_INTERRUPT = "direct_question_pattern_interrupt"
    PROBLEM_THEN_PROMISE = "problem_then_promise"
    CHALLENGE_STATEMENT = "challenge_statement"
    ESTABLISHING_CONTEXT = "establishing_context"
    NUMBERED_PROMISE = "numbered_promise"


class AspectRatio(str, enum.Enum):
    VERTICAL = "9:16"
    HORIZONTAL = "16:9"


class Pacing(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    avg_clip_seconds: float = Field(gt=0, description="target seconds per generated video clip")
    cuts_style: str = Field(min_length=1, description="descriptive tag consumed by the assembly stage")


class NicheProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$",
                    description="snake_case, stable — the DB key, never renamed once jobs reference it")
    display_name: str = Field(min_length=1)
    script_system_prompt: str = Field(min_length=1)
    hook_style: HookStyle
    pacing: Pacing
    visual_prompt_modifiers: str = Field(min_length=1)
    voice_tone: str = Field(min_length=1)
    music_mood: str = Field(min_length=1)
    caption_style: str = Field(min_length=1)
    aspect_default: AspectRatio
    needs_tts: bool

    @property
    def is_placeholder(self) -> bool:
        """True while the prompt text still carries Appendix A's PLACEHOLDER marker."""
        return "PLACEHOLDER" in self.script_system_prompt or "PLACEHOLDER" in self.visual_prompt_modifiers


# Names of every field a stage can rely on. Used by tests and the seeder.
NICHE_PROFILE_FIELDS: tuple[str, ...] = tuple(NicheProfile.model_fields.keys())


class NicheProfileError(Exception):
    """Base class for niche profile lookup failures."""


class NicheProfileNotFound(NicheProfileError):
    def __init__(self, niche_id: str):
        self.niche_id = niche_id
        super().__init__(f"Niche profile not found: {niche_id!r}. Check the id against niche_profiles.")


class NicheProfileInvalid(NicheProfileError):
    """The stored row exists but does not satisfy the NicheProfile schema."""
    def __init__(self, niche_id: str, detail: str):
        self.niche_id = niche_id
        super().__init__(f"Niche profile {niche_id!r} is invalid and was not returned: {detail}")
