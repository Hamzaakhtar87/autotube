"""
Phase 3 — LLM adapter unit tests (all provider HTTP mocked with respx).

Covers: success per provider, the fallback order (configured and default),
needs_tts carried through from the profile, every failure classification
mapped to our own human-readable, provider-named wording, and — with every
mocked error body deliberately echoing the planted key — that nothing the
adapter emits contains credentials (the session-wide leak sweep watches too).
"""
import json

import httpx
import pytest
import respx

from app.niches.seed import load_profiles_file
from runner.llm_adapter import (
    ANTHROPIC_MESSAGES_URL,
    DEFAULT_SCRIPT_PROVIDER_ORDER,
    GEMINI_GENERATE_URL_TEMPLATE,
    GROQ_CHAT_URL,
    OPENAI_CHAT_URL,
    SCRIPT_MODELS,
    FailureReason,
    Provider,
    ScriptGenerationFailed,
    VideoFormat,
    generate_script,
    parse_scenes,
    resolve_provider_order,
)
from tests.planted import PLANTED_API_KEY

PROFILES = {p.id: p for p in load_profiles_file()}
TRUE_CRIME = PROFILES["true_crime_narration"]
WHATIF = PROFILES["whatif_hypothetical"]
TOPIC = "The Dyatlov Pass incident"

SAMPLE_RAW = """[SCENE]
SPEECH: Nine hikers walked into the Ural mountains. Only their tent came back intact.
VISUAL: Snow-covered mountain pass at dusk
[/SCENE]
[SCENE]
SPEECH: The tent was cut open from the inside. Their boots were still in it.
VISUAL: Torn canvas tent half buried in snow
[/SCENE]
[SCENE]
SPEECH: Sixty years later, no explanation fits every fact.
VISUAL: Old case files and photographs on a desk
[/SCENE]"""

GEMINI_URL = GEMINI_GENERATE_URL_TEMPLATE.format(model=SCRIPT_MODELS[Provider.gemini])

# Success bodies per provider shape.
ANTHROPIC_OK = {"content": [{"type": "text", "text": SAMPLE_RAW}]}
OPENAI_OK = {"choices": [{"message": {"role": "assistant", "content": SAMPLE_RAW}}]}
GEMINI_OK = {"candidates": [{"content": {"parts": [{"text": SAMPLE_RAW}]}}]}

# Error bodies deliberately echo the planted key — the adapter must never
# let that text reach a message, a log, or an exception.
ECHOING_ERROR = {"error": {"message": f"bad key {PLANTED_API_KEY}", "type": "invalid_request_error"}}


@pytest.fixture(autouse=True)
def fast_retries(monkeypatch):
    """Retries are real in prod; the 15s pause is not welcome in a test run."""
    monkeypatch.setattr("runner.llm_adapter.time.sleep", lambda s: None)


def planted_lookup(provider):
    return {"api_key": PLANTED_API_KEY}


def only(providers):
    """key_lookup that has a key for the given providers only."""
    def lookup(provider):
        return {"api_key": PLANTED_API_KEY} if provider in providers else None
    return lookup


class TestSuccess:
    @respx.mock
    def test_first_provider_wins_and_fields_are_complete(self):
        route = respx.post(ANTHROPIC_MESSAGES_URL).respond(200, json=ANTHROPIC_OK)
        script = generate_script(TRUE_CRIME, TOPIC, "short", key_lookup=planted_lookup)
        assert route.called
        assert script.provider is Provider.anthropic
        assert script.niche_id == "true_crime_narration"
        assert script.topic == TOPIC
        assert script.format is VideoFormat.short
        assert len(script.scenes) == 3
        assert script.scenes[0].speech.startswith("Nine hikers")
        assert script.scenes[0].visual == "Snow-covered mountain pass at dusk"
        assert script.word_count == len(script.full_text.split()) > 0
        assert script.estimated_duration_seconds == pytest.approx(script.word_count / 2.5, abs=0.1)
        assert script.failed_attempts == ()

    @respx.mock
    def test_needs_tts_carried_through_untouched(self):
        respx.post(ANTHROPIC_MESSAGES_URL).respond(200, json=ANTHROPIC_OK)
        assert generate_script(TRUE_CRIME, TOPIC, key_lookup=planted_lookup).needs_tts is True
        assert generate_script(WHATIF, TOPIC, key_lookup=planted_lookup).needs_tts is False

    @respx.mock
    def test_each_provider_response_shape_parses(self):
        respx.post(ANTHROPIC_MESSAGES_URL).respond(200, json=ANTHROPIC_OK)
        respx.post(OPENAI_CHAT_URL).respond(200, json=OPENAI_OK)
        respx.post(GROQ_CHAT_URL).respond(200, json=OPENAI_OK)
        respx.post(GEMINI_URL).respond(200, json=GEMINI_OK)
        for provider in DEFAULT_SCRIPT_PROVIDER_ORDER:
            script = generate_script(TRUE_CRIME, TOPIC, key_lookup=planted_lookup, order=[provider])
            assert script.provider is provider
            assert len(script.scenes) == 3

    @respx.mock
    def test_prompt_carries_profile_and_hook_rule(self):
        route = respx.post(ANTHROPIC_MESSAGES_URL).respond(200, json=ANTHROPIC_OK)
        generate_script(WHATIF, TOPIC, key_lookup=planted_lookup)
        body = json.loads(route.calls.last.request.content)
        assert body["system"] == WHATIF.script_system_prompt
        user = body["messages"][0]["content"]
        assert TOPIC in user
        assert "What if" in user  # the whatif hook rule made it into the prompt
        assert body["model"] == SCRIPT_MODELS[Provider.anthropic]


class TestFallback:
    @respx.mock
    def test_invalid_key_falls_through_to_next_provider(self):
        respx.post(ANTHROPIC_MESSAGES_URL).respond(401, json=ECHOING_ERROR)
        respx.post(OPENAI_CHAT_URL).respond(200, json=OPENAI_OK)
        script = generate_script(TRUE_CRIME, TOPIC, key_lookup=planted_lookup)
        assert script.provider is Provider.openai
        (attempt,) = script.failed_attempts
        assert attempt.provider is Provider.anthropic
        assert attempt.reason is FailureReason.invalid_key
        assert "Anthropic (Claude)" in attempt.message
        assert PLANTED_API_KEY not in attempt.message

    @respx.mock
    def test_missing_keys_are_skipped_with_named_attempts(self):
        respx.post(GEMINI_URL).respond(200, json=GEMINI_OK)
        script = generate_script(TRUE_CRIME, TOPIC, key_lookup=only({Provider.gemini}))
        assert script.provider is Provider.gemini
        assert [a.provider for a in script.failed_attempts] == [Provider.anthropic, Provider.openai]
        assert all(a.reason is FailureReason.missing_key for a in script.failed_attempts)
        assert "no API key is saved" in script.failed_attempts[0].message

    @respx.mock
    def test_unparseable_output_falls_through(self):
        respx.post(ANTHROPIC_MESSAGES_URL).respond(
            200, json={"content": [{"type": "text", "text": "Sorry, here is an essay instead."}]}
        )
        respx.post(OPENAI_CHAT_URL).respond(200, json=OPENAI_OK)
        script = generate_script(TRUE_CRIME, TOPIC, key_lookup=planted_lookup)
        assert script.provider is Provider.openai
        assert script.failed_attempts[0].reason is FailureReason.empty_script

    @respx.mock
    def test_custom_order_only_calls_named_provider(self):
        groq = respx.post(GROQ_CHAT_URL).respond(200, json=OPENAI_OK)
        anthropic = respx.post(ANTHROPIC_MESSAGES_URL).respond(200, json=ANTHROPIC_OK)
        script = generate_script(TRUE_CRIME, TOPIC, key_lookup=planted_lookup, order="groq")
        assert script.provider is Provider.groq
        assert groq.called and not anthropic.called


class TestAllProvidersFail:
    def test_no_keys_at_all_names_every_provider_and_explains(self):
        with pytest.raises(ScriptGenerationFailed) as exc_info:
            generate_script(TRUE_CRIME, TOPIC, key_lookup=lambda p: None)
        failure = exc_info.value
        assert len(failure.attempts) == 4
        message = failure.user_message
        for label in ("Anthropic (Claude)", "OpenAI", "Google Gemini", "Groq"):
            assert label in message
        assert "no API key is saved" in message
        assert "Settings" in message
        # Human wording, not a stack trace or exception repr.
        assert "Traceback" not in message and "Exception" not in message

    @respx.mock
    def test_mixed_failures_each_get_their_own_wording(self):
        respx.post(ANTHROPIC_MESSAGES_URL).respond(401, json=ECHOING_ERROR)
        respx.post(OPENAI_CHAT_URL).respond(
            429, json={"error": {"type": "insufficient_quota", "message": f"quota {PLANTED_API_KEY}"}}
        )
        respx.post(GEMINI_URL).mock(side_effect=httpx.ConnectTimeout("boom"))
        with pytest.raises(ScriptGenerationFailed) as exc_info:
            generate_script(TRUE_CRIME, TOPIC, key_lookup=only(
                {Provider.anthropic, Provider.openai, Provider.gemini}))
        reasons = {a.provider: a.reason for a in exc_info.value.attempts}
        assert reasons[Provider.anthropic] is FailureReason.invalid_key
        assert reasons[Provider.openai] is FailureReason.no_credit
        assert reasons[Provider.gemini] is FailureReason.timeout
        assert reasons[Provider.groq] is FailureReason.missing_key
        assert PLANTED_API_KEY not in exc_info.value.user_message
        assert PLANTED_API_KEY not in repr(exc_info.value)

    @respx.mock
    def test_gemini_400_api_key_invalid_classified(self):
        respx.post(GEMINI_URL).respond(
            400,
            json={"error": {"message": f"API key not valid {PLANTED_API_KEY}",
                            "details": [{"reason": "API_KEY_INVALID"}]}},
        )
        with pytest.raises(ScriptGenerationFailed) as exc_info:
            generate_script(TRUE_CRIME, TOPIC, key_lookup=only({Provider.gemini}), order="gemini")
        (attempt,) = exc_info.value.attempts
        assert attempt.reason is FailureReason.invalid_key
        assert PLANTED_API_KEY not in attempt.message

    @respx.mock
    def test_retired_model_404_classified_as_model_unavailable(self):
        # Shaped from the real 2026-10 response: Google 404s a retired model
        # with advice text (which must not be passed through either).
        respx.post(GEMINI_URL).respond(
            404,
            json={"error": {"code": 404, "status": "NOT_FOUND",
                            "message": f"This model is no longer available {PLANTED_API_KEY}"}},
        )
        with pytest.raises(ScriptGenerationFailed) as exc_info:
            generate_script(TRUE_CRIME, TOPIC, key_lookup=only({Provider.gemini}), order="gemini")
        (attempt,) = exc_info.value.attempts
        assert attempt.reason is FailureReason.model_unavailable
        assert "no longer serves the model" in attempt.message
        assert PLANTED_API_KEY not in attempt.message

    @respx.mock
    def test_transient_503_retried_once_then_succeeds(self):
        # Real case (2026-10): Gemini 503 "high demand" on one call, fine on
        # the next. One in-place retry must rescue it instead of falling
        # through to unconfigured providers.
        route = respx.post(GEMINI_URL)
        route.side_effect = [
            httpx.Response(503, json={"error": {"code": 503, "status": "UNAVAILABLE",
                                                "message": f"high demand {PLANTED_API_KEY}"}}),
            httpx.Response(200, json=GEMINI_OK),
        ]
        script = generate_script(TRUE_CRIME, TOPIC, key_lookup=only({Provider.gemini}), order="gemini")
        assert script.provider is Provider.gemini
        assert script.failed_attempts == ()  # the retry rescued it silently
        assert route.call_count == 2

    @respx.mock
    def test_persistent_503_classified_as_provider_unavailable(self):
        route = respx.post(GEMINI_URL).respond(503, json=ECHOING_ERROR)
        with pytest.raises(ScriptGenerationFailed) as exc_info:
            generate_script(TRUE_CRIME, TOPIC, key_lookup=only({Provider.gemini}), order="gemini")
        (attempt,) = exc_info.value.attempts
        assert attempt.reason is FailureReason.provider_unavailable
        assert "temporarily overloaded" in attempt.message
        assert PLANTED_API_KEY not in attempt.message
        assert route.call_count == 2  # original + one retry, no more

    @respx.mock
    def test_non_retryable_failure_not_retried(self):
        route = respx.post(GEMINI_URL).respond(401, json=ECHOING_ERROR)
        with pytest.raises(ScriptGenerationFailed):
            generate_script(TRUE_CRIME, TOPIC, key_lookup=only({Provider.gemini}), order="gemini")
        assert route.call_count == 1

    @respx.mock
    def test_rate_limited_and_network_error_classified(self):
        respx.post(GROQ_CHAT_URL).respond(429, json=ECHOING_ERROR)
        respx.post(OPENAI_CHAT_URL).mock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(ScriptGenerationFailed) as exc_info:
            generate_script(TRUE_CRIME, TOPIC,
                            key_lookup=only({Provider.groq, Provider.openai}),
                            order=["groq", "openai"])
        reasons = {a.provider: a.reason for a in exc_info.value.attempts}
        assert reasons[Provider.groq] is FailureReason.rate_limited
        assert reasons[Provider.openai] is FailureReason.network_error


class TestOrderParsing:
    def test_none_gives_default(self):
        assert resolve_provider_order(None) == DEFAULT_SCRIPT_PROVIDER_ORDER

    def test_comma_string_and_list_forms(self):
        assert resolve_provider_order("gemini, groq") == (Provider.gemini, Provider.groq)
        assert resolve_provider_order(["groq", Provider.anthropic]) == (Provider.groq, Provider.anthropic)

    def test_unknown_video_duplicate_and_empty_rejected(self):
        with pytest.raises(ValueError, match="unknown"):
            resolve_provider_order("chatgpt")
        with pytest.raises(ValueError, match="video provider"):
            resolve_provider_order("kling")
        with pytest.raises(ValueError, match="duplicate"):
            resolve_provider_order("groq,groq")
        with pytest.raises(ValueError, match="empty"):
            resolve_provider_order([])


class TestSceneParser:
    def test_markdown_and_continuation_lines(self):
        raw = "**[SCENE]**\nSPEECH: First line\ncontinues here.\nVISUAL: A thing\n[/SCENE]"
        (scene,) = parse_scenes(raw)
        assert scene.speech == "First line continues here."
        assert scene.visual == "A thing"

    def test_prose_without_scenes_yields_nothing(self):
        assert parse_scenes("Here is a lovely essay about mountains.") == []
