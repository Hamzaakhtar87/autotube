"""
Phase 3 — AI-powered hook-style contrast check (rough, by design).

Generates a true-crime script and a what-if script on the SAME topic with a
real provider, then:
  1. string check — the what-if script opens with a "what if" framing and the
     true-crime one does not;
  2. one LLM-judge call — same/different verdict with a one-line reason;
     the verdict must be "different".

Opt-in (it spends real tokens and needs the network), so the default suite
stays offline and deterministic:

    AUTOTUBE_AI_TESTS=1 python -m pytest tests/test_script_style_ai.py -v -s

Uses GEMINI_API_KEY / GROQ_API_KEY etc. from the environment (the repo .env
is loaded by the app package).
"""
import os

import pytest

from app.niches.seed import load_profiles_file
from runner.llm_adapter import HOOK_STYLE_RULES, generate_script
from runner.sample_scripts import env_key_lookup
from runner.style_judge import judge_hook_contrast

pytestmark = [
    pytest.mark.ai_judge,
    pytest.mark.skipif(
        os.environ.get("AUTOTUBE_AI_TESTS") != "1",
        reason="real-LLM test; set AUTOTUBE_AI_TESTS=1 to run",
    ),
]

TOPIC = "The Dyatlov Pass incident"


@pytest.fixture(scope="module")
def scripts():
    profiles = {p.id: p for p in load_profiles_file()}
    true_crime = generate_script(profiles["true_crime_narration"], TOPIC, "short",
                                 key_lookup=env_key_lookup)
    whatif = generate_script(profiles["whatif_hypothetical"], TOPIC, "short",
                             key_lookup=env_key_lookup)
    return profiles, true_crime, whatif


def test_hook_strings_differ(scripts):
    _, true_crime, whatif = scripts
    whatif_open = whatif.scenes[0].speech.lower()
    crime_open = true_crime.scenes[0].speech.lower()
    assert whatif_open.startswith("what if"), f"whatif hook was: {whatif.scenes[0].speech!r}"
    assert not crime_open.startswith("what if"), f"true-crime hook was: {true_crime.scenes[0].speech!r}"


def test_llm_judge_says_different(scripts):
    profiles, true_crime, whatif = scripts
    verdict = judge_hook_contrast(
        true_crime, HOOK_STYLE_RULES[profiles["true_crime_narration"].hook_style],
        whatif, HOOK_STYLE_RULES[profiles["whatif_hypothetical"].hook_style],
        key_lookup=env_key_lookup,
    )
    print(f"\nJUDGE ({verdict.provider.value}): {verdict.verdict} — {verdict.reason}")
    assert verdict.verdict == "different", f"judge said same: {verdict.reason}"
    assert verdict.reason  # the one-line reason must actually be there
