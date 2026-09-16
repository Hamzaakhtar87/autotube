"""
Phase 2 test (3): every API route except the job-execution decrypt path.

A user saves all seven planted keys. Then every route the app registers —
enumerated from `app.routes`, not typed by hand, and pinned to EXPECTED_ROUTES
so a route added later can't silently skip this — is called as the key's
owner and as an admin. No response may contain a planted secret or the stored
ciphertext. Also covered: the static `/output` mount, the import boundary
around `runner/vault_decrypt.py`, decrypt refusing without the private key,
and Supabase's PostgREST returning nothing from `provider_keys` with the anon key.
"""
import os
import pathlib
import re
from unittest.mock import patch

import httpx
import pytest
import respx
from fastapi.routing import APIRoute
from starlette.routing import Mount, Route

from app.main import app
from app.models.models import ProviderKey, User
from tests import vault_mocks as M
from tests.planted import PLANTED_SECRETS, credentials_for

PROVIDERS = ["anthropic", "openai", "groq", "gemini", "kling", "veo", "seedance"]

# Every (method, path) the app exposes. If this drifts from app.routes the
# test fails: update the list *and* make sure the new route can't return a key.
EXPECTED_ROUTES = [
    ("GET", "/"),
    ("GET", "/admin/health"),
    ("GET", "/admin/jobs"),
    ("GET", "/admin/stats"),
    ("GET", "/admin/users"),
    ("DELETE", "/admin/users/{user_id}"),
    ("PATCH", "/admin/users/{user_id}"),
    ("POST", "/api/webhooks/geminigen"),
    ("POST", "/auth/change-password"),
    ("POST", "/auth/forgot-password"),
    ("POST", "/auth/login"),
    ("POST", "/auth/logout"),
    ("POST", "/auth/logout-all"),
    ("GET", "/auth/me"),
    ("PATCH", "/auth/me"),
    ("POST", "/auth/refresh"),
    ("POST", "/auth/register"),
    ("POST", "/auth/resend-verification"),
    ("POST", "/auth/reset-password"),
    ("POST", "/auth/token"),
    ("POST", "/auth/verify-email"),
    ("GET", "/auth/youtube/callback"),
    ("POST", "/auth/youtube/disconnect"),
    ("GET", "/auth/youtube/url"),
    ("POST", "/billing/create-checkout-session"),
    ("POST", "/billing/create-portal-session"),
    ("GET", "/billing/subscription"),
    ("POST", "/billing/webhook"),
    ("GET", "/competitors/"),
    ("POST", "/competitors/"),
    ("GET", "/config/preferences"),
    ("POST", "/config/preferences"),
    ("GET", "/config/profile"),
    ("POST", "/config/secrets"),
    ("GET", "/config/status"),
    ("GET", "/docs"),
    ("HEAD", "/docs"),
    ("GET", "/docs/oauth2-redirect"),
    ("HEAD", "/docs/oauth2-redirect"),
    ("GET", "/health"),
    ("GET", "/jobs"),
    ("POST", "/jobs"),
    ("GET", "/jobs/{job_id}"),
    ("POST", "/jobs/{job_id}/stop"),
    ("GET", "/keys"),
    ("DELETE", "/keys/{provider}"),
    ("PUT", "/keys/{provider}"),
    ("POST", "/keys/{provider}/test"),
    ("GET", "/openapi.json"),
    ("HEAD", "/openapi.json"),
    ("MOUNT", "/output"),
    ("GET", "/overview"),
    ("GET", "/redoc"),
    ("HEAD", "/redoc"),
    ("POST", "/sync"),
    ("GET", "/usage"),
    ("GET", "/videos"),
    ("GET", "/videos/{video_id}/download"),
    ("GET", "/workspaces/"),
    ("POST", "/workspaces/"),
]

# Path params: values that exist for the owner where it matters, and
# non-existent ids where the route would otherwise mutate a real record.
PATH_PARAMS = {"{user_id}": "999999", "{job_id}": "999999", "{video_id}": "999999", "{provider}": "veo"}

WRITE_METHODS = ("POST", "PUT", "PATCH")

# Bodies that get past parsing so the handler itself runs.
BODIES = {
    ("POST", "/config/preferences"): {},
    ("PATCH", "/auth/me"): {"full_name": "Sweep"},
    ("POST", "/jobs"): {"config": {"topic": "sweep"}},
    ("POST", "/config/secrets"): {"nothing": True},
}


def registered_routes():
    rows = set()
    for r in app.routes:
        if isinstance(r, APIRoute):
            rows.update((m, r.path) for m in r.methods)
        elif isinstance(r, Mount):
            rows.add(("MOUNT", r.path))
        elif isinstance(r, Route):
            rows.update((m, r.path) for m in (r.methods or []))
        else:
            rows.add((type(r).__name__, getattr(r, "path", "?")))
    return sorted(rows, key=lambda x: (x[1], x[0]))


@pytest.fixture(scope="module")
def vault_users(client):
    """Owner with all 7 keys saved; an admin; the owner's stored ciphertexts."""
    from tests.conftest import TestingSessionLocal, register_and_login

    with respx.mock(assert_all_called=False) as m:
        M.mock_ok(m)
        owner_email, owner = register_and_login(client, "sweepowner")
        for p in PROVIDERS:
            assert client.put(f"/keys/{p}", json=credentials_for(p), headers=owner).status_code == 200
    admin_email, admin = register_and_login(client, "sweepadmin")
    db = TestingSessionLocal()
    try:
        db.query(User).filter(User.email == admin_email).update({"is_admin": True})
        db.commit()
        owner_id = db.query(User).filter(User.email == owner_email).one().id
        ciphertexts = [r.ciphertext for r in db.query(ProviderKey).filter(ProviderKey.user_id == owner_id).all()]
    finally:
        db.close()
    assert len(ciphertexts) == 7
    return {"owner": owner, "admin": admin, "owner_id": owner_id, "ciphertexts": ciphertexts}


def test_route_list_is_pinned():
    assert registered_routes() == sorted(EXPECTED_ROUTES, key=lambda x: (x[1], x[0])), (
        "app.routes changed — add the route to EXPECTED_ROUTES after confirming it can't return a key"
    )


def _call(client, method, path, headers):
    for k, v in PATH_PARAMS.items():
        path = path.replace(k, v)
    if method == "MOUNT":
        return [client.get(path + "/", headers=headers), client.get(path + "/anything.mp4", headers=headers)]
    if method in WRITE_METHODS:
        return [client.request(method, path, headers=headers, json=BODIES.get((method, path), {}))]
    return [client.request(method, path, headers=headers)]


@pytest.mark.parametrize("who", ["owner", "admin"])
@pytest.mark.parametrize("method,path", EXPECTED_ROUTES, ids=[f"{m} {p}" for m, p in EXPECTED_ROUTES])
def test_route_never_returns_a_key(client, vault_users, who, method, path):
    forbidden = list(PLANTED_SECRETS) + vault_users["ciphertexts"]
    with patch("app.api.jobs.dispatch_job"), respx.mock(assert_all_called=False, assert_all_mocked=False) as m:
        # Any outbound provider call (e.g. PUT /keys/veo with an empty body never gets
        # this far, but be safe) is answered with a body that echoes the secrets.
        m.route().mock(return_value=httpx.Response(401, json={"error": {"message": M.ECHO}}))
        responses = _call(client, method, path, vault_users[who])
    if method == "DELETE" and path.startswith("/keys/") and who == "owner":
        # The sweep just deleted the owner's real row; put it back for the tests after this one.
        prov = PATH_PARAMS["{provider}"]
        with respx.mock(assert_all_called=False) as m2:
            M.mock_ok(m2, [prov])
            assert client.put(f"/keys/{prov}", json=credentials_for(prov), headers=vault_users["owner"]).status_code == 200
    for resp in responses:
        blob = resp.text + repr(dict(resp.headers))
        for s in forbidden:
            assert s not in blob, f"{who} {method} {path} -> {resp.status_code} leaked {s[:16]}…"
        # Never a 500: the sanitizer would hide a traceback but a traceback is still a bug.
        assert resp.status_code != 500, f"{who} {method} {path} -> 500: {resp.text[:200]}"


def test_keys_list_has_no_secret_shaped_fields(client, vault_users):
    res = client.get("/keys", headers=vault_users["owner"]).json()
    for row in res["providers"]:
        assert set(row) == {"provider", "label", "fields", "configured", "last_tested_at", "last_test_status"}
        assert row["configured"] is True
    text = str(res)
    assert not re.search(r"ciphertext|api_key\W*:|secret_key\W*:|access_key\W*:", text)


def test_openapi_has_no_route_that_returns_key_material(client):
    spec = client.get("/openapi.json").json()
    schemas = spec.get("components", {}).get("schemas", {})
    for name, schema in schemas.items():
        if name in ("KeySubmission",):
            continue  # request-only
        for prop in schema.get("properties", {}):
            assert prop not in ("ciphertext", "api_key", "secret_key", "access_key", "plaintext"), f"{name}.{prop} in a response schema"


# --- code-level guarantees -------------------------------------------------

BACKEND = pathlib.Path(__file__).resolve().parent.parent


def test_only_runner_imports_the_decrypt_module():
    importers = []
    for py in BACKEND.rglob("*.py"):
        if "venv" in py.parts or ".venv" in py.parts or "tests" in py.parts:
            continue  # tests exercise the decrypt path on purpose; shipped code is what's audited
        text = py.read_text(errors="ignore")
        if re.search(r"^\s*(from|import)\s+runner\.vault_decrypt|^\s*from\s+runner\s+import\s+vault_decrypt", text, re.M):
            importers.append(py.relative_to(BACKEND).as_posix())
    assert sorted(importers) == ["runner/provider_keys.py"], importers


def test_app_package_never_imports_runner():
    offenders = []
    for py in (BACKEND / "app").rglob("*.py"):
        if re.search(r"^\s*(from|import)\s+runner\b", py.read_text(errors="ignore"), re.M):
            offenders.append(py.relative_to(BACKEND).as_posix())
    assert offenders == []


def test_app_has_no_decrypt_capability():
    """No SealedBox with a PrivateKey, no nacl secret-key primitives, anywhere under app/."""
    for py in (BACKEND / "app").rglob("*.py"):
        text = py.read_text(errors="ignore")
        assert "PrivateKey" not in text, py
        assert "SecretBox" not in text, py
        assert ".decrypt(" not in text or py.name == "security.py", py  # legacy Fernet helper for YouTube OAuth creds


def test_load_provider_key_refuses_in_api_process(vault_users, db_session):
    from runner.provider_keys import load_provider_key
    from runner.vault_decrypt import VaultPrivateKeyUnavailable
    assert "VAULT_PRIVATE_KEY" not in os.environ
    with pytest.raises(VaultPrivateKeyUnavailable):
        load_provider_key(vault_users["owner_id"], "openai", db_session)


def test_load_provider_key_round_trips_in_runner(vault_users, db_session, vault_private_key, monkeypatch):
    """With the runner's private key present, job execution gets the credentials back."""
    from runner.provider_keys import load_provider_key
    monkeypatch.setenv("VAULT_PRIVATE_KEY", vault_private_key)
    try:
        for p in PROVIDERS:
            assert load_provider_key(vault_users["owner_id"], p, db_session) == credentials_for(p)
    finally:
        monkeypatch.delenv("VAULT_PRIVATE_KEY")
    assert "VAULT_PRIVATE_KEY" not in os.environ


# --- Supabase PostgREST with the public anon key ---------------------------

def _supabase_public_creds():
    """Env first, else the repo's gitignored .env (app.core.config looks for backend/.env, not this one)."""
    from dotenv import dotenv_values
    values = dotenv_values(BACKEND.parent / ".env")
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or values.get("NEXT_PUBLIC_SUPABASE_URL")
    anon = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") or values.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    return url, anon


@pytest.mark.skipif(not all(_supabase_public_creds()), reason="Supabase URL/anon key not configured")
def test_supabase_anon_cannot_read_provider_keys():
    """Live check against the real project: the public anon key gets nothing from provider_keys."""
    base, anon = _supabase_public_creds()
    url = base.rstrip("/") + "/rest/v1/provider_keys?select=*"
    with respx.mock(assert_all_mocked=False) as m:
        m.route(host=httpx.URL(url).host).pass_through()
        resp = httpx.get(url, headers={"apikey": anon, "Authorization": f"Bearer {anon}"}, timeout=15)
    # RLS on with no policies and no grant: PostgREST answers 401/403 (or 404 if
    # the table is hidden from the schema cache). A 200 must be an empty list.
    assert resp.status_code in (401, 403, 404) or resp.json() == [], (resp.status_code, resp.text[:200])
    for s in PLANTED_SECRETS:
        assert s not in resp.text
