"""
/keys routes: save / test / delete flows and the per-provider result mapping.
All provider HTTP is mocked with respx; nothing leaves the machine.
"""
import httpx
import pytest
import respx

from app.vault.testers import TestStatus
from tests import vault_mocks as M
from tests.conftest import register_and_login
from tests.planted import PLANTED_API_KEY, PLANTED_KLING_ACCESS_KEY, PLANTED_KLING_SECRET_KEY, credentials_for

PROVIDERS = ["anthropic", "openai", "groq", "gemini", "kling", "veo", "seedance"]


def _auth(client, prefix):
    _, headers = register_and_login(client, prefix)
    return headers


def _find(rows, provider):
    return next(r for r in rows if r["provider"] == provider)


def _provider_row(client, headers, provider):
    """The caller's /keys row for one provider."""
    return _find(client.get("/keys", headers=headers).json()["providers"], provider)


@pytest.fixture
def headers(client):
    return _auth(client, "keys")


@pytest.fixture
def mock():
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as m:
        yield m


# --- listing ---------------------------------------------------------------

def test_list_requires_auth(client):
    assert client.get("/keys").status_code in (401, 403)


def test_list_shows_all_seven_unconfigured(client, headers):
    res = client.get("/keys", headers=headers)
    assert res.status_code == 200
    rows = res.json()["providers"]
    assert [r["provider"] for r in rows] == PROVIDERS
    assert all(r["configured"] is False and r["last_test_status"] is None for r in rows)
    assert _find(rows, "kling")["fields"] == ["access_key", "secret_key"]
    assert _find(rows, "veo")["fields"] == ["api_key"]


# --- test -> save -> list -> delete, every provider ---------------------------

@pytest.mark.parametrize("provider", PROVIDERS)
def test_full_flow(client, headers, mock, provider):
    M.mock_ok(mock)
    creds = credentials_for(provider)

    t = client.post(f"/keys/{provider}/test", json=creds, headers=headers)
    assert t.status_code == 200, t.text
    assert t.json() == {"provider": provider, "status": "ok", "ok": True, "message": "Key accepted by the provider."}
    # test stores nothing
    assert _provider_row(client, headers, provider)["configured"] is False

    s = client.put(f"/keys/{provider}", json=creds, headers=headers)
    assert s.status_code == 200, s.text
    body = s.json()
    assert body["saved"] is True and body["ok"] is True and body["warning"] is False
    assert set(body) == {"provider", "status", "ok", "message", "saved", "warning"}

    row = _provider_row(client, headers, provider)
    assert row["configured"] is True
    assert row["last_test_status"] == "ok"
    assert row["last_tested_at"] is not None
    assert set(row) == {"provider", "label", "fields", "configured", "last_tested_at", "last_test_status"}

    d = client.delete(f"/keys/{provider}", headers=headers)
    assert d.status_code == 200 and d.json() == {"provider": provider, "deleted": True}
    assert client.delete(f"/keys/{provider}", headers=headers).json()["deleted"] is False
    assert _provider_row(client, headers, provider)["configured"] is False


def test_update_replaces_existing_row(client, headers, mock, db_session):
    from app.models.models import ProviderKey
    M.mock_ok(mock)
    assert client.put("/keys/openai", json={"api_key": PLANTED_API_KEY}, headers=headers).status_code == 200
    first = db_session.query(ProviderKey).filter_by(provider="openai").order_by(ProviderKey.id.desc()).first()
    first_id, first_user, first_ct = first.id, first.user_id, first.ciphertext
    assert client.put("/keys/openai", json={"api_key": PLANTED_API_KEY + "-v2"}, headers=headers).status_code == 200
    db_session.expire_all()
    rows = db_session.query(ProviderKey).filter_by(user_id=first_user, provider="openai").all()
    assert len(rows) == 1 and rows[0].id == first_id and rows[0].ciphertext != first_ct
    assert PLANTED_API_KEY not in rows[0].ciphertext


def test_keys_are_per_user(client, mock):
    M.mock_ok(mock)
    a, b = _auth(client, "usera"), _auth(client, "userb")
    assert client.put("/keys/groq", json={"api_key": PLANTED_API_KEY}, headers=a).status_code == 200
    assert _provider_row(client, b, "groq")["configured"] is False
    assert client.delete("/keys/groq", headers=b).json()["deleted"] is False
    assert _provider_row(client, a, "groq")["configured"] is True


# --- save refuses bad keys, saves rate-limited with a warning ------------------

def test_save_refuses_invalid_key(client, headers, mock):
    M.mock_status(mock, "openai", 401)
    res = client.put("/keys/openai", json={"api_key": PLANTED_API_KEY}, headers=headers)
    assert res.status_code == 400
    assert res.json()["detail"] == {"status": "invalid_key", "message": "The provider rejected this key as invalid.", "saved": False}
    assert _provider_row(client, headers, "openai")["configured"] is False


@pytest.mark.parametrize("status", [TestStatus.no_credit, TestStatus.no_permission, TestStatus.timeout, TestStatus.network_error, TestStatus.unexpected_response])
def test_save_refuses_every_non_saveable_status(client, headers, mock, status):
    if status is TestStatus.timeout:
        M.mock_exception(mock, "anthropic", httpx.ReadTimeout("slow"))
    elif status is TestStatus.network_error:
        M.mock_exception(mock, "anthropic", httpx.ConnectError("down"))
    else:
        M.mock_status(mock, "anthropic", {TestStatus.no_credit: 402, TestStatus.no_permission: 403, TestStatus.unexpected_response: 500}[status])
    res = client.put("/keys/anthropic", json={"api_key": PLANTED_API_KEY}, headers=headers)
    assert res.status_code == 400 and res.json()["detail"]["status"] == status.value


def test_rate_limited_key_is_saved_with_warning(client, headers, mock):
    M.mock_status(mock, "groq", 429, body={"error": {"message": M.ECHO, "type": "rate_limit_exceeded"}})
    res = client.put("/keys/groq", json={"api_key": PLANTED_API_KEY}, headers=headers)
    assert res.status_code == 200
    assert res.json()["saved"] is True and res.json()["warning"] is True and res.json()["status"] == "rate_limited"
    row = _provider_row(client, headers, "groq")
    assert row["configured"] is True and row["last_test_status"] == "rate_limited"


# --- per-provider status mapping ---------------------------------------------

def _test_status(client, headers, provider):
    return client.post(f"/keys/{provider}/test", json=credentials_for(provider), headers=headers).json()["status"]


@pytest.mark.parametrize("provider", ["anthropic", "openai", "groq", "seedance"])
@pytest.mark.parametrize("http,expected", [(401, "invalid_key"), (402, "no_credit"), (403, "no_permission"), (429, "rate_limited"), (500, "unexpected_response"), (404, "unexpected_response")])
def test_bearer_providers_map_http_status(client, headers, mock, provider, http, expected):
    M.mock_status(mock, provider, http)
    assert _test_status(client, headers, provider) == expected


def test_openai_insufficient_quota_is_no_credit(client, headers, mock):
    M.mock_status(mock, "openai", 429, body={"error": {"message": M.ECHO, "type": "insufficient_quota", "code": "insufficient_quota"}})
    assert _test_status(client, headers, "openai") == "no_credit"


@pytest.mark.parametrize("provider", ["gemini", "veo"])
def test_gemini_api_key_invalid(client, headers, mock, provider):
    M.mock_status(mock, provider, 400, body={"error": {"code": 400, "message": "API key not valid. " + M.ECHO, "status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}})
    assert _test_status(client, headers, provider) == "invalid_key"
    M.mock_status(mock, provider, 403, body={"error": {"code": 403, "message": M.ECHO, "status": "PERMISSION_DENIED"}})
    assert _test_status(client, headers, provider) == "no_permission"
    M.mock_status(mock, provider, 429, body={"error": {"code": 429, "message": M.ECHO, "status": "RESOURCE_EXHAUSTED"}})
    assert _test_status(client, headers, provider) == "rate_limited"


def test_veo_requires_a_veo_model(client, headers, mock):
    M.mock_veo_without_veo_models(mock)
    res = client.post("/keys/veo/test", json={"api_key": PLANTED_API_KEY}, headers=headers).json()
    assert res["status"] == "no_permission" and "Veo" in res["message"]
    assert client.put("/keys/veo", json={"api_key": PLANTED_API_KEY}, headers=headers).status_code == 400


@pytest.mark.parametrize("code,expected", [(1000, "invalid_key"), (1002, "invalid_key"), (1004, "invalid_key"), (1101, "no_credit"), (1102, "no_credit"), (1103, "no_permission"), (1302, "rate_limited"), (1303, "rate_limited"), (5000, "unexpected_response")])
def test_kling_maps_service_codes(client, headers, mock, code, expected):
    M.mock_status(mock, "kling", 200 if code == 5000 else 429, body=M.kling_body(code))
    assert _test_status(client, headers, "kling") == expected


def test_kling_sends_signed_jwt_not_the_secret(client, headers, mock):
    from jose import jwt
    M.mock_ok(mock, ["kling"])
    assert _test_status(client, headers, "kling") == "ok"
    req = mock.calls.last.request
    token = req.headers["Authorization"].removeprefix("Bearer ")
    assert PLANTED_KLING_SECRET_KEY not in str(req.url) + str(dict(req.headers))
    claims = jwt.decode(token, PLANTED_KLING_SECRET_KEY, algorithms=["HS256"], options={"verify_exp": False})
    assert claims["iss"] == PLANTED_KLING_ACCESS_KEY and claims["exp"] - claims["nbf"] == 1805


def test_kling_requires_both_fields(client, headers, mock):
    res = client.post("/keys/kling/test", json={"api_key": PLANTED_API_KEY}, headers=headers)
    assert res.status_code == 422 and "api_key" in res.json()["detail"] and PLANTED_API_KEY not in res.text
    res = client.post("/keys/kling/test", json={"access_key": PLANTED_KLING_ACCESS_KEY}, headers=headers)
    assert res.status_code == 422 and "secret_key is required" in res.json()["detail"]


def test_seedance_overdue_is_no_credit(client, headers, mock):
    status, body = M.seedance_error("AccountOverdueError", 403)
    M.mock_status(mock, "seedance", status, body=body)
    assert _test_status(client, headers, "seedance") == "no_credit"


def test_gemini_key_travels_in_header_not_url(client, headers, mock):
    M.mock_ok(mock, ["gemini"])
    assert _test_status(client, headers, "gemini") == "ok"
    req = mock.calls.last.request
    assert PLANTED_API_KEY not in str(req.url)
    assert req.headers["x-goog-api-key"] == PLANTED_API_KEY


# --- input validation never echoes the key -----------------------------------

def test_validation_errors_do_not_echo_input(client, headers):
    res = client.post("/keys/openai/test", json={"api_key": PLANTED_API_KEY, "bogus": 1}, headers=headers)
    assert res.status_code == 422 and PLANTED_API_KEY not in res.text
    res = client.post("/keys/openai/test", json={"api_key": ["not", "a", "string", PLANTED_API_KEY]}, headers=headers)
    assert res.status_code == 422 and PLANTED_API_KEY not in res.text
    for err in res.json()["detail"]:
        assert set(err) <= {"loc", "msg", "type"}
    res = client.post("/keys/notaprovider/test", json={"api_key": PLANTED_API_KEY}, headers=headers)
    assert res.status_code == 422 and PLANTED_API_KEY not in res.text
    res = client.put("/keys/openai", json={"api_key": ""}, headers=headers)
    assert res.status_code == 422
    res = client.put("/keys/openai", json={"api_key": "x" * 600}, headers=headers)
    assert res.status_code == 422 and "x" * 600 not in res.text


def test_vault_unconfigured_is_503_not_plaintext_save(client, headers, mock, monkeypatch, db_session):
    from app.models.models import ProviderKey
    M.mock_ok(mock)
    monkeypatch.setenv("VAULT_PUBLIC_KEY", "")
    res = client.put("/keys/anthropic", json={"api_key": PLANTED_API_KEY}, headers=headers)
    assert res.status_code == 503
    assert PLANTED_API_KEY not in "".join(r.ciphertext for r in db_session.query(ProviderKey).all())
