"""
Phase 3 LLM adapter: (niche_profile, topic, format) -> Script.

Routes through the script-capable providers — Anthropic, OpenAI, Gemini,
Groq — in a configurable fallback order (DEFAULT_SCRIPT_PROVIDER_ORDER).
Credentials come from a `key_lookup` callable so this module never touches
the DB or the vault; job execution passes a closure over
`runner.provider_keys.load_provider_key`, the sample CLI passes one over
environment variables.

Error handling mirrors app/vault/testers.py: provider error text is NEVER
passed through (some providers echo the key back in error bodies). Every
failure maps to our own fixed, human-readable wording that names the
provider — the exact strings job_logs will carry. The only log line per
attempt is provider name + outcome, no credentials, no bodies.
"""
from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Callable, Mapping, Sequence

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.niches.schema import HookStyle, NicheProfile
from app.vault.providers import PROVIDER_LABELS, Provider

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 120.0  # a full script generation, not a key ping

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_GENERATE_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

# The four providers that can write a script (kling/veo/seedance are video).
SCRIPT_PROVIDERS: tuple[Provider, ...] = (
    Provider.anthropic,
    Provider.openai,
    Provider.gemini,
    Provider.groq,
)

# Quality-first: niche contrast is the product, so the strongest
# style-followers go first. Ordering by quality costs nothing in robustness
# because every failure (missing key, no credit, invalid) falls through to
# the next configured provider — a $0-balance user whose only working key is
# a free-tier Gemini or Groq key still lands on it.
DEFAULT_SCRIPT_PROVIDER_ORDER: tuple[Provider, ...] = (
    Provider.anthropic,
    Provider.openai,
    Provider.gemini,
    Provider.groq,
)

SCRIPT_MODELS: dict[Provider, str] = {
    Provider.anthropic: "claude-sonnet-4-5",
    Provider.openai: "gpt-4o",
    # Pinned, not the "-latest" alias: Google retired gemini-2.5-flash for
    # new keys (2026-10) and its 404 recommended 3.8; the gemini-flash-latest
    # alias was tried first but its pool threw sustained 503s while the
    # concrete model served fine. A future retirement fails loudly as
    # model_unavailable, so pinning no longer rots silently.
    Provider.gemini: "gemini-3.8-flash",
    Provider.groq: "llama-3.3-70b-versatile",
}

# A callable mapping a provider to its decrypted credentials, or None when
# the user has no key saved for it. Matches load_provider_key's return shape.
KeyLookup = Callable[[Provider], Mapping[str, str] | None]


def lookup_api_key(key_lookup: KeyLookup, provider: Provider) -> str:
    """The provider's api_key from `key_lookup`, or "" when none is saved."""
    return (key_lookup(provider) or {}).get("api_key", "")


class VideoFormat(str, Enum):
    short = "short"
    long = "long"


FORMAT_TARGET_SECONDS: dict[VideoFormat, tuple[int, int]] = {
    VideoFormat.short: (45, 60),
    VideoFormat.long: (180, 300),
}

SPOKEN_WORDS_PER_SECOND = 2.5  # same speech-rate estimate the legacy pipeline used


# --- Failure taxonomy ------------------------------------------------------

class FailureReason(str, Enum):
    missing_key = "missing_key"
    invalid_key = "invalid_key"
    no_credit = "no_credit"
    no_permission = "no_permission"
    rate_limited = "rate_limited"
    timeout = "timeout"
    network_error = "network_error"
    model_unavailable = "model_unavailable"
    provider_unavailable = "provider_unavailable"
    unexpected_response = "unexpected_response"
    empty_script = "empty_script"


FAILURE_WORDING: dict[FailureReason, str] = {
    FailureReason.missing_key: "no API key is saved for this provider. Add one in Settings → API Keys.",
    FailureReason.invalid_key: "the saved API key was rejected as invalid. Replace it in Settings → API Keys.",
    FailureReason.no_credit: "the key works but the account has no credit or an unpaid balance.",
    FailureReason.rate_limited: "the provider is rate limiting this key right now. Try again in a few minutes.",
    FailureReason.no_permission: "the key does not have permission to use this model.",
    FailureReason.timeout: f"the provider did not answer within {TIMEOUT_SECONDS:.0f} seconds.",
    FailureReason.network_error: "the provider could not be reached.",
    FailureReason.model_unavailable: (
        "the provider no longer serves the model this app requests. "
        "The app's model list needs an update — please report this."
    ),
    FailureReason.provider_unavailable: (
        "the provider is temporarily overloaded or down. Try again in a few minutes."
    ),
    FailureReason.unexpected_response: "the provider returned an unexpected response.",
    FailureReason.empty_script: "the model replied but produced no usable script scenes.",
}


# A transient condition (rate limit, overload) gets one in-place retry before
# the adapter falls through to the next provider — otherwise a momentary 503
# burns the user's only configured provider and fails the whole job.
PROVIDER_RETRIES = 1
RETRY_DELAY_SECONDS = 15.0
RETRYABLE_REASONS = frozenset({FailureReason.rate_limited, FailureReason.provider_unavailable})


class ProviderAttempt(BaseModel):
    """One failed try at one provider, in words fit for the job log."""
    model_config = ConfigDict(frozen=True)

    provider: Provider
    reason: FailureReason
    message: str  # "<label>: <our wording>", never provider text


def _attempt(provider: Provider, reason: FailureReason) -> ProviderAttempt:
    return ProviderAttempt(
        provider=provider,
        reason=reason,
        message=f"{PROVIDER_LABELS[provider]}: {FAILURE_WORDING[reason]}",
    )


class ScriptGenerationFailed(Exception):
    """Every provider in the fallback order failed. Message is job-log ready."""

    def __init__(self, attempts: Sequence[ProviderAttempt]):
        self.attempts = list(attempts)
        super().__init__(self.user_message)

    @property
    def user_message(self) -> str:
        if not self.attempts:
            return (
                "Script generation failed: no script provider is configured. "
                "Add an Anthropic, OpenAI, Gemini, or Groq key in Settings → API Keys."
            )
        details = " ".join(a.message for a in self.attempts)
        return f"Script generation failed — no provider produced a script. {details}"


class _CallFailed(Exception):
    """Internal: one provider call failed, classified. Carries no provider text."""

    def __init__(self, reason: FailureReason):
        self.reason = reason
        super().__init__(reason.value)


# --- Script output ---------------------------------------------------------

class Scene(BaseModel):
    model_config = ConfigDict(frozen=True)
    speech: str = Field(min_length=1)
    visual: str = Field(min_length=1)


class Script(BaseModel):
    """What the script stage hands to the rest of the pipeline."""
    model_config = ConfigDict(frozen=True)

    niche_id: str
    topic: str
    format: VideoFormat
    provider: Provider
    model: str
    scenes: tuple[Scene, ...] = Field(min_length=1)
    full_text: str
    word_count: int
    estimated_duration_seconds: float
    # Carried through from the niche profile untouched — Phase 5/6 decide
    # what to do with it. No narration logic lives here.
    needs_tts: bool
    # Providers that failed before this one succeeded (for the job log).
    failed_attempts: tuple[ProviderAttempt, ...] = ()


# --- Prompt construction ----------------------------------------------------

HOOK_STYLE_RULES: dict[HookStyle, str] = {
    HookStyle.COLD_OPEN_QUESTION: (
        "Open cold, mid-story, with an unsettling question or unresolved detail "
        "that pulls the viewer in. Do NOT open with 'What if'."
    ),
    HookStyle.DIRECT_QUESTION_PATTERN_INTERRUPT: (
        "The very first spoken sentence MUST be a direct question beginning with "
        "the words 'What if' — a pattern interrupt that stops the scroll."
    ),
    HookStyle.PROBLEM_THEN_PROMISE: (
        "Open by naming a concrete problem the viewer recognises, then promise "
        "what they'll understand by the end."
    ),
    HookStyle.CHALLENGE_STATEMENT: (
        "Open with a blunt second-person challenge aimed straight at the viewer."
    ),
    HookStyle.ESTABLISHING_CONTEXT: (
        "Open by establishing time, place, and stakes before making any claim."
    ),
    HookStyle.NUMBERED_PROMISE: (
        "Open by promising a specific number of items, then deliver them as a "
        "clearly numbered list."
    ),
}

MIN_SCENES, MAX_SCENES = 4, 30


def plan_scenes(profile: NicheProfile, format: VideoFormat) -> tuple[int, int]:
    """(scene_count, words_per_scene) from the format's target length and the
    niche's pacing — fast-cut niches get more, shorter scenes."""
    lo, hi = FORMAT_TARGET_SECONDS[format]
    target = (lo + hi) / 2
    count = max(MIN_SCENES, min(MAX_SCENES, round(target / profile.pacing.avg_clip_seconds)))
    words_per_scene = max(8, round((target / count) * SPOKEN_WORDS_PER_SECOND))
    return count, words_per_scene


def build_prompts(profile: NicheProfile, topic: str, format: VideoFormat) -> tuple[str, str]:
    """(system, user). The niche's script_system_prompt IS the system prompt;
    structure and the hook rule go in the user message."""
    lo, hi = FORMAT_TARGET_SECONDS[format]
    scene_count, words_per_scene = plan_scenes(profile, format)
    kind = "YouTube Short" if format is VideoFormat.short else "YouTube video"
    user = f"""Write the complete narration script for a {kind} about: {topic}

Opening rule (non-negotiable): {HOOK_STYLE_RULES[profile.hook_style]}

Structure:
- Exactly {scene_count} scenes.
- Each scene's SPEECH is roughly {words_per_scene} words; the whole script must run {lo}-{hi} seconds spoken at a natural pace.
- Each scene's VISUAL is a short description of what is on screen (max 12 words). Describe content only — no camera or style directions, those are added later.
- The last scene closes the video; no meta-commentary, no hashtags.

Output format (strict — nothing before, between, or after the scene blocks):
[SCENE]
SPEECH: ...
VISUAL: ...
[/SCENE]"""
    return profile.script_system_prompt, user


# --- Output parsing ---------------------------------------------------------

def parse_scenes(raw: str) -> list[Scene]:
    """Line-based SPEECH:/VISUAL: parser. Tolerates markdown bolding and
    continuation lines; ignores anything outside a recognised field."""
    text = raw.replace("**", "").replace("*", "")
    scenes: list[Scene] = []
    speech, visual, mode = "", "", None

    def flush() -> None:
        nonlocal speech, visual, mode
        if speech.strip() and visual.strip():
            scenes.append(Scene(speech=" ".join(speech.split()), visual=" ".join(visual.split())))
        speech, visual, mode = "", "", None

    for line in text.splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith(("[SCENE", "[/SCENE")):
            flush()
        elif upper.startswith(("SPEECH:", "SPEECH :")):
            if speech.strip() and visual.strip():
                flush()
            mode = "speech"
            speech = stripped.split(":", 1)[1] + " "
        elif upper.startswith(("VISUAL:", "VISUAL :")):
            mode = "visual"
            visual = stripped.split(":", 1)[1] + " "
        elif stripped and mode == "speech":
            speech += stripped + " "
        elif stripped and mode == "visual":
            visual += stripped + " "
    flush()
    return scenes


# --- Provider calls ---------------------------------------------------------

def _json(resp: httpx.Response) -> dict:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


REASON_BY_HTTP_CODE = {
    401: FailureReason.invalid_key,
    402: FailureReason.no_credit,
    403: FailureReason.no_permission,
    # 404 from a generate endpoint = the pinned model was retired/renamed
    # (Google did this to gemini-2.5-flash while still listing it, 2026-10).
    404: FailureReason.model_unavailable,
    429: FailureReason.rate_limited,
    500: FailureReason.provider_unavailable,
    502: FailureReason.provider_unavailable,
    503: FailureReason.provider_unavailable,
    504: FailureReason.provider_unavailable,
}


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code == 200:
        return
    if resp.status_code == 429:
        err = _json(resp).get("error") or {}
        if isinstance(err, dict) and "insufficient_quota" in str(err.get("code", "")) + str(err.get("type", "")):
            raise _CallFailed(FailureReason.no_credit)
    raise _CallFailed(REASON_BY_HTTP_CODE.get(resp.status_code, FailureReason.unexpected_response))


def _call_anthropic(client: httpx.Client, api_key: str, model: str, system: str, user: str) -> str:
    resp = client.post(
        ANTHROPIC_MESSAGES_URL,
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        json={
            "model": model,
            "max_tokens": 4096,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
    )
    _raise_for_status(resp)
    blocks = _json(resp).get("content") or []
    return "\n".join(b.get("text", "") for b in blocks if isinstance(b, dict))


def _call_openai_compatible(client: httpx.Client, url: str, api_key: str, model: str, system: str, user: str) -> str:
    resp = client.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "max_tokens": 4096,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
    )
    _raise_for_status(resp)
    choices = _json(resp).get("choices") or []
    if choices and isinstance(choices[0], dict):
        return str((choices[0].get("message") or {}).get("content") or "")
    return ""


def _call_gemini(client: httpx.Client, api_key: str, model: str, system: str, user: str) -> str:
    # Key goes in a header, never in the query string, so it can't land in URL logs.
    resp = client.post(
        GEMINI_GENERATE_URL_TEMPLATE.format(model=model),
        headers={"x-goog-api-key": api_key},
        json={
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"maxOutputTokens": 8192},
        },
    )
    if resp.status_code == 400:
        err = _json(resp).get("error") or {}
        details = err.get("details") if isinstance(err, dict) else None
        reasons = {d.get("reason") for d in (details or []) if isinstance(d, dict)}
        if "API_KEY_INVALID" in reasons or "API key not valid" in str(err.get("message", "")):
            raise _CallFailed(FailureReason.invalid_key)
        raise _CallFailed(FailureReason.unexpected_response)
    _raise_for_status(resp)
    candidates = _json(resp).get("candidates") or []
    if candidates and isinstance(candidates[0], dict):
        parts = (candidates[0].get("content") or {}).get("parts") or []
        return "\n".join(p.get("text", "") for p in parts if isinstance(p, dict))
    return ""


def complete_text(provider: Provider, api_key: str, system: str, user: str, model: str | None = None) -> str:
    """One plain system+user completion against one provider. Raises _CallFailed
    (classified, no provider text). Also used by the style judge."""
    model = model or SCRIPT_MODELS[provider]
    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            if provider is Provider.anthropic:
                return _call_anthropic(client, api_key, model, system, user)
            if provider is Provider.openai:
                return _call_openai_compatible(client, OPENAI_CHAT_URL, api_key, model, system, user)
            if provider is Provider.groq:
                return _call_openai_compatible(client, GROQ_CHAT_URL, api_key, model, system, user)
            if provider is Provider.gemini:
                return _call_gemini(client, api_key, model, system, user)
    except _CallFailed:
        raise
    except httpx.TimeoutException:
        raise _CallFailed(FailureReason.timeout)
    except httpx.HTTPError:
        raise _CallFailed(FailureReason.network_error)
    except Exception:
        # Deliberately no exception text: an HTTP/SDK error string can echo the key.
        raise _CallFailed(FailureReason.unexpected_response)
    raise _CallFailed(FailureReason.unexpected_response)  # not a script provider


# --- Fallback order ----------------------------------------------------------

def resolve_provider_order(order: Sequence[Provider | str] | str | None) -> tuple[Provider, ...]:
    """Normalise a configured order ("gemini,groq", ["groq", ...], None) to
    Provider members. Unknown or non-script providers fail loudly."""
    if order is None:
        return DEFAULT_SCRIPT_PROVIDER_ORDER
    if isinstance(order, str):
        order = [part.strip() for part in order.split(",") if part.strip()]
    resolved: list[Provider] = []
    for item in order:
        try:
            provider = Provider(item)
        except ValueError:
            raise ValueError(f"unknown script provider in fallback order: {item!r}")
        if provider not in SCRIPT_PROVIDERS:
            raise ValueError(f"{provider.value} is a video provider, not a script provider")
        if provider in resolved:
            raise ValueError(f"duplicate provider in fallback order: {provider.value}")
        resolved.append(provider)
    if not resolved:
        raise ValueError("script provider fallback order is empty")
    return tuple(resolved)


# --- The adapter entry point --------------------------------------------------

def generate_script(
    niche_profile: NicheProfile,
    topic: str,
    format: VideoFormat | str = VideoFormat.short,
    *,
    key_lookup: KeyLookup,
    order: Sequence[Provider | str] | str | None = None,
) -> Script:
    """Generate a niche-styled script, falling through the provider order.

    Returns a Script (with any earlier failures in .failed_attempts) or raises
    ScriptGenerationFailed whose .attempts / .user_message are job-log ready.
    """
    format = VideoFormat(format)
    providers = resolve_provider_order(order)
    system, user = build_prompts(niche_profile, topic, format)

    attempts: list[ProviderAttempt] = []

    def record_failure(provider: Provider, reason: FailureReason) -> None:
        attempts.append(_attempt(provider, reason))
        log.info("script provider=%s status=%s", provider.value, reason.value)

    for provider in providers:
        api_key = lookup_api_key(key_lookup, provider)
        if not api_key:
            record_failure(provider, FailureReason.missing_key)
            continue
        raw = None
        for try_no in range(1 + PROVIDER_RETRIES):
            try:
                raw = complete_text(provider, api_key, system, user)
                break
            except _CallFailed as failure:
                if failure.reason in RETRYABLE_REASONS and try_no < PROVIDER_RETRIES:
                    log.info("script provider=%s status=%s retrying in %ss",
                             provider.value, failure.reason.value, RETRY_DELAY_SECONDS)
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
                record_failure(provider, failure.reason)
                break
        if raw is None:
            continue
        scenes = parse_scenes(raw)
        if not scenes:
            record_failure(provider, FailureReason.empty_script)
            continue
        full_text = " ".join(s.speech for s in scenes)
        word_count = len(full_text.split())
        log.info("script provider=%s status=ok scenes=%d", provider.value, len(scenes))
        return Script(
            niche_id=niche_profile.id,
            topic=topic,
            format=format,
            provider=provider,
            model=SCRIPT_MODELS[provider],
            scenes=tuple(scenes),
            full_text=full_text,
            word_count=word_count,
            estimated_duration_seconds=round(word_count / SPOKEN_WORDS_PER_SECOND, 1),
            needs_tts=niche_profile.needs_tts,
            failed_attempts=tuple(attempts),
        )
    raise ScriptGenerationFailed(attempts)
