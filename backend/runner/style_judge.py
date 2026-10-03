"""
AI-powered hook-style check (Phase 3's slice of the Phase 8 judge layer).

One LLM call: both scripts go to a judge which answers whether their
openings follow the same hook style or genuinely different ones, with a
one-line reason. Rough by design — the authoritative judge pass is Phase 8.
"""
from __future__ import annotations

from typing import Sequence

from pydantic import BaseModel, ConfigDict

from runner.llm_adapter import (
    KeyLookup,
    Provider,
    Script,
    _CallFailed,
    complete_text,
    lookup_api_key,
    resolve_provider_order,
)

JUDGE_SYSTEM = (
    "You are a strict judge of YouTube script openings. You answer in exactly "
    "two lines:\nVERDICT: same|different\nREASON: <one short sentence>"
)

JUDGE_USER_TEMPLATE = """Two YouTube scripts open below. Judge ONLY the opening hooks (the first one or two spoken sentences of each), not the topics — both scripts are deliberately about the same topic.

Expected style for Script A ({style_a}): {rule_a}
Expected style for Script B ({style_b}): {rule_b}

Do the two openings follow the SAME hook style, or genuinely DIFFERENT hook styles?

--- Script A ---
{script_a}

--- Script B ---
{script_b}

Answer in exactly two lines:
VERDICT: same|different
REASON: <one short sentence>"""


class JudgeVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)
    verdict: str  # "same" | "different"
    reason: str
    provider: Provider


def _opening(script: Script, scene_count: int = 2) -> str:
    return "\n".join(f"SPEECH: {s.speech}" for s in script.scenes[:scene_count])


def judge_hook_contrast(
    script_a: Script,
    rule_a: str,
    script_b: Script,
    rule_b: str,
    *,
    key_lookup: KeyLookup,
    order: Sequence[Provider | str] | str | None = None,
) -> JudgeVerdict:
    """Ask one configured LLM whether the two hooks read as different styles."""
    user = JUDGE_USER_TEMPLATE.format(
        style_a=script_a.niche_id, rule_a=rule_a,
        style_b=script_b.niche_id, rule_b=rule_b,
        script_a=_opening(script_a), script_b=_opening(script_b),
    )
    failures: list[str] = []
    for provider in resolve_provider_order(order):
        api_key = lookup_api_key(key_lookup, provider)
        if not api_key:
            failures.append(f"{provider.value}: no key")
            continue
        try:
            raw = complete_text(provider, api_key, JUDGE_SYSTEM, user)
        except _CallFailed as failure:
            failures.append(f"{provider.value}: {failure.reason.value}")
            continue
        verdict, reason = _parse_verdict(raw)
        if verdict:
            return JudgeVerdict(verdict=verdict, reason=reason, provider=provider)
        failures.append(f"{provider.value}: unparseable verdict")
    raise RuntimeError(f"no provider could judge the scripts ({'; '.join(failures)})")


def _parse_verdict(raw: str) -> tuple[str, str]:
    verdict, reason = "", ""
    for line in raw.splitlines():
        upper = line.strip().upper()
        if upper.startswith("VERDICT:"):
            value = line.split(":", 1)[1].strip().lower()
            if "different" in value:
                verdict = "different"
            elif "same" in value:
                verdict = "same"
        elif upper.startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()
    return verdict, reason
