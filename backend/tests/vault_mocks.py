"""respx fixtures for the seven provider "test key" calls.

Every error body deliberately echoes the submitted credential back (some real
providers do), so the leak sweep proves the API strips it.
"""
import httpx
import respx

from app.vault import testers as T
from tests.planted import PLANTED_API_KEY, PLANTED_KLING_ACCESS_KEY, PLANTED_KLING_SECRET_KEY

ECHO = f"Incorrect API key provided: {PLANTED_API_KEY}. kling ak={PLANTED_KLING_ACCESS_KEY} sk={PLANTED_KLING_SECRET_KEY}"

URLS = {
    "anthropic": T.ANTHROPIC_MODELS_URL,
    "openai": T.OPENAI_MODELS_URL,
    "groq": T.GROQ_MODELS_URL,
    "gemini": T.GEMINI_MODELS_URL,
    "veo": T.GEMINI_MODELS_URL,
    "kling": T.KLING_COSTS_URL,
    "seedance": T.SEEDANCE_TASKS_URL,
}

OK_BODIES = {
    "anthropic": {"data": [{"id": "claude-sonnet-5", "type": "model"}]},
    "openai": {"object": "list", "data": [{"id": "gpt-5"}]},
    "groq": {"object": "list", "data": [{"id": "llama-3.3-70b-versatile"}]},
    "gemini": {"models": [{"name": "models/gemini-2.5-flash"}]},
    "veo": {"models": [{"name": "models/gemini-2.5-flash"}, {"name": "models/veo-3.0-generate-preview"}]},
    "kling": {"code": 0, "message": "SUCCEED", "request_id": "r1", "data": {"code": 0, "resource_pack_subscribe_infos": []}},
    "seedance": {"items": [], "total": 0},
}


def route(provider: str, mock: respx.MockRouter):
    return mock.get(url__startswith=URLS[provider])


def mock_ok(mock: respx.MockRouter, providers=None):
    for p in providers if providers is not None else URLS:
        route(p, mock).mock(return_value=httpx.Response(200, json=OK_BODIES[p]))


def mock_status(mock: respx.MockRouter, provider: str, status: int, body=None):
    if body is None:
        body = {"error": {"message": ECHO, "type": "invalid_request_error", "code": "invalid_api_key"}}
    route(provider, mock).mock(return_value=httpx.Response(status, json=body))


def mock_exception(mock: respx.MockRouter, provider: str, exc: Exception):
    route(provider, mock).mock(side_effect=exc)


def mock_veo_without_veo_models(mock: respx.MockRouter):
    route("veo", mock).mock(return_value=httpx.Response(200, json=OK_BODIES["gemini"]))


def kling_body(code: int):
    return {"code": code, "message": ECHO, "request_id": "r-err"}


def seedance_error(code: str, status: int):
    return status, {"error": {"code": code, "message": ECHO, "type": "Forbidden"}}
