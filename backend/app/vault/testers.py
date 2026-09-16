"""
"Test key": one minimal, real call per provider.

Every tester returns a `TestResult` with a status from `TestStatus` and a
message written by us. Provider error text is never passed through — some
providers echo the key back in their error bodies — and nothing in here logs
a request, a response body, or a credential. The only log line is the
provider name and the resulting status.

Calls (all read-only, free or as close to free as the provider offers):
  anthropic  GET https://api.anthropic.com/v1/models
  openai     GET https://api.openai.com/v1/models
  groq       GET https://api.groq.com/openai/v1/models
  gemini     GET https://generativelanguage.googleapis.com/v1beta/models   (key in header)
  veo        same as gemini, then requires a veo-* model in the list
  kling      GET https://api-singapore.klingai.com/account/costs  (JWT from AK+SK; documented free)
  seedance   GET https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks?page_num=1&page_size=1
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum

import httpx
from jose import jwt

from app.vault.providers import Provider

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10.0

ANTHROPIC_MODELS_URL = "https://api.anthropic.com/v1/models"
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
KLING_BASE_URL = "https://api-singapore.klingai.com"
KLING_COSTS_URL = f"{KLING_BASE_URL}/account/costs"
SEEDANCE_TASKS_URL = "https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks"


class TestStatus(str, Enum):
    ok = "ok"
    invalid_key = "invalid_key"
    no_credit = "no_credit"
    no_permission = "no_permission"
    rate_limited = "rate_limited"
    timeout = "timeout"
    network_error = "network_error"
    unexpected_response = "unexpected_response"


# Statuses under which PUT /keys/{provider} will still store the key.
SAVEABLE = {TestStatus.ok, TestStatus.rate_limited}

MESSAGES = {
    TestStatus.ok: "Key accepted by the provider.",
    TestStatus.invalid_key: "The provider rejected this key as invalid.",
    TestStatus.no_credit: "The key is valid but the account has no credit or an unpaid balance.",
    TestStatus.no_permission: "The key is valid but does not have access to this API.",
    TestStatus.rate_limited: "The provider is rate limiting this key right now; it was accepted but could not be fully verified.",
    TestStatus.timeout: "The provider did not answer within 10 seconds.",
    TestStatus.network_error: "Could not reach the provider.",
    TestStatus.unexpected_response: "The provider returned an unexpected response.",
}


@dataclass(frozen=True)
class TestResult:
    status: TestStatus
    message: str = ""

    def __post_init__(self):
        if not self.message:
            object.__setattr__(self, "message", MESSAGES[self.status])

    @property
    def ok(self) -> bool:
        return self.status is TestStatus.ok

    @property
    def saveable(self) -> bool:
        return self.status in SAVEABLE


def _json(resp: httpx.Response) -> dict:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


STATUS_BY_HTTP_CODE = {
    200: TestStatus.ok,
    401: TestStatus.invalid_key,
    402: TestStatus.no_credit,
    403: TestStatus.no_permission,
    429: TestStatus.rate_limited,
}


def _by_http_status(resp: httpx.Response) -> TestResult:
    return TestResult(STATUS_BY_HTTP_CODE.get(resp.status_code, TestStatus.unexpected_response))


# --- OpenAI-compatible (OpenAI, Groq) -------------------------------------

def _openai_compatible(client: httpx.Client, url: str, api_key: str) -> TestResult:
    resp = client.get(url, headers={"Authorization": f"Bearer {api_key}"})
    if resp.status_code == 429:
        err = _json(resp).get("error") or {}
        if isinstance(err, dict) and "insufficient_quota" in str(err.get("code", "")) + str(err.get("type", "")):
            return TestResult(TestStatus.no_credit)
    return _by_http_status(resp)


def _test_openai(client: httpx.Client, creds: dict[str, str]) -> TestResult:
    return _openai_compatible(client, OPENAI_MODELS_URL, creds["api_key"])


def _test_groq(client: httpx.Client, creds: dict[str, str]) -> TestResult:
    return _openai_compatible(client, GROQ_MODELS_URL, creds["api_key"])


# --- Anthropic -----------------------------------------------------------

def _test_anthropic(client: httpx.Client, creds: dict[str, str]) -> TestResult:
    resp = client.get(
        ANTHROPIC_MODELS_URL,
        headers={"x-api-key": creds["api_key"], "anthropic-version": "2023-06-01"},
    )
    return _by_http_status(resp)


# --- Gemini / Veo --------------------------------------------------------

def _gemini_models(client: httpx.Client, api_key: str) -> tuple[TestResult, list]:
    # Key goes in a header, never in the query string, so it can't land in URL logs.
    resp = client.get(GEMINI_MODELS_URL, headers={"x-goog-api-key": api_key})
    if resp.status_code == 400:
        err = _json(resp).get("error") or {}
        details = err.get("details") if isinstance(err, dict) else None
        reasons = {d.get("reason") for d in (details or []) if isinstance(d, dict)}
        if "API_KEY_INVALID" in reasons or "API key not valid" in str(err.get("message", "")):
            return TestResult(TestStatus.invalid_key), []
        return TestResult(TestStatus.unexpected_response), []
    result = _by_http_status(resp)
    models = _json(resp).get("models") if result.ok else []
    return result, models if isinstance(models, list) else []


def _test_gemini(client: httpx.Client, creds: dict[str, str]) -> TestResult:
    result, _ = _gemini_models(client, creds["api_key"])
    return result


def _test_veo(client: httpx.Client, creds: dict[str, str]) -> TestResult:
    result, models = _gemini_models(client, creds["api_key"])
    if not result.ok:
        return result
    if any("veo" in str(m.get("name", "")).lower() for m in models if isinstance(m, dict)):
        return result
    return TestResult(TestStatus.no_permission, "The Gemini key works but lists no Veo model. Enable Veo for this key in Google AI Studio.")


# --- Kling ---------------------------------------------------------------

# Kling answers with its own service code in the body; the HTTP status is 429
# for most of them, so the body code decides.
KLING_STATUS_BY_CODE = {
    0: TestStatus.ok,
    **dict.fromkeys((1000, 1001, 1002, 1003, 1004), TestStatus.invalid_key),
    **dict.fromkeys((1100, 1101, 1102), TestStatus.no_credit),
    1103: TestStatus.no_permission,
    **dict.fromkeys((1302, 1303), TestStatus.rate_limited),
}


def kling_jwt(access_key: str, secret_key: str, now: int | None = None) -> str:
    now = int(now if now is not None else time.time())
    return jwt.encode(
        {"iss": access_key, "exp": now + 1800, "nbf": now - 5},
        secret_key,
        algorithm="HS256",
        headers={"alg": "HS256", "typ": "JWT"},
    )


def _test_kling(client: httpx.Client, creds: dict[str, str]) -> TestResult:
    token = kling_jwt(creds["access_key"], creds["secret_key"])
    now_ms = int(time.time() * 1000)
    resp = client.get(
        KLING_COSTS_URL,
        params={"start_time": now_ms - 24 * 3600 * 1000, "end_time": now_ms},
        headers={"Authorization": f"Bearer {token}"},
    )
    code = _json(resp).get("code")
    if isinstance(code, int):
        status = KLING_STATUS_BY_CODE.get(code)
        if status is not None:
            return TestResult(status)
        if resp.status_code == 200:
            return TestResult(TestStatus.unexpected_response)
    return _by_http_status(resp)


# --- Seedance (BytePlus ModelArk) ----------------------------------------

def _test_seedance(client: httpx.Client, creds: dict[str, str]) -> TestResult:
    resp = client.get(
        SEEDANCE_TASKS_URL,
        params={"page_num": 1, "page_size": 1},
        headers={"Authorization": f"Bearer {creds['api_key']}"},
    )
    if resp.status_code in (403, 429):
        err = _json(resp).get("error") or {}
        code = str(err.get("code", "")) if isinstance(err, dict) else ""
        if "Overdue" in code or "Quota" in code:
            return TestResult(TestStatus.no_credit)
    return _by_http_status(resp)


TESTERS = {
    Provider.anthropic: _test_anthropic,
    Provider.openai: _test_openai,
    Provider.groq: _test_groq,
    Provider.gemini: _test_gemini,
    Provider.veo: _test_veo,
    Provider.kling: _test_kling,
    Provider.seedance: _test_seedance,
}


def run_key_test(provider: Provider, credentials: dict[str, str]) -> TestResult:
    """Fire the provider's minimal call. Never raises; never logs credentials."""
    tester = TESTERS[Provider(provider)]
    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
            result = tester(client, credentials)
    except httpx.TimeoutException:
        result = TestResult(TestStatus.timeout)
    except httpx.HTTPError:
        result = TestResult(TestStatus.network_error)
    except Exception:
        # Deliberately no exception text: a provider SDK/HTTP error string can echo the key.
        result = TestResult(TestStatus.unexpected_response)
    log.info("key test provider=%s status=%s", Provider(provider).value, result.status.value)
    return result
