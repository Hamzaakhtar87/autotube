"""
Test Configuration
Uses a separate test database to avoid polluting production data.
Set TEST_DATABASE_URL to point at a Postgres instance; without it the suite
falls back to a throwaway local SQLite file.

Vault (Phase 2): a throwaway sealed-box keypair is generated per run. The
public half goes into the environment before the app imports (so the API can
encrypt); the private half stays in this module and is handed to the decrypt
tests explicitly — VAULT_PRIVATE_KEY is scrubbed from the environment so the
API process genuinely cannot decrypt.

Leak sweep: everything the run emits (log records at DEBUG, captured
stdout/stderr, every API response body and header, the raw provider_keys
column) is collected and grepped for the planted secrets in `planted.py` at
session end. A hit fails the whole session.
"""
import base64
import logging
import os
import sys
import uuid

import pytest

# Add backend to path so 'app' module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Override DATABASE_URL BEFORE any app imports
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test_autotube.db")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# Throwaway vault keypair for this run (before app import: app.core.config
# loads .env with override=False, so this wins over any VAULT_PUBLIC_KEY there).
from nacl.public import PrivateKey  # noqa: E402

_TEST_VAULT_SK = PrivateKey.generate()
TEST_VAULT_PRIVATE_KEY_B64 = base64.b64encode(bytes(_TEST_VAULT_SK)).decode()
TEST_VAULT_PUBLIC_KEY_B64 = base64.b64encode(bytes(_TEST_VAULT_SK.public_key)).decode()
os.environ["VAULT_PUBLIC_KEY"] = TEST_VAULT_PUBLIC_KEY_B64
os.environ.pop("VAULT_PRIVATE_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from app.main import app  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from tests.planted import PLANTED_SECRETS  # noqa: E402

# .env is loaded by app.core.config; make sure it didn't smuggle the private key in.
assert "VAULT_PRIVATE_KEY" not in os.environ, "VAULT_PRIVATE_KEY must never be set where the API runs"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False} if TEST_DATABASE_URL.startswith("sqlite") else {},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


# ---------------------------------------------------------------------------
# Leak-sweep collection
# ---------------------------------------------------------------------------

class _Collected:
    logs: list = []
    stdout: list = []
    stderr: list = []
    responses: list = []  # (method, url, status, headers-as-text, body-text)


COLLECTED = _Collected()


class _CollectingHandler(logging.Handler):
    def emit(self, record):
        try:
            COLLECTED.logs.append(self.format(record))
        except Exception:
            COLLECTED.logs.append(repr(record.__dict__))


_root = logging.getLogger()
_root.setLevel(logging.DEBUG)
_handler = _CollectingHandler(level=logging.DEBUG)
_handler.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))
_root.addHandler(_handler)


class RecordingTestClient(TestClient):
    """TestClient that keeps every response body + headers for the end-of-run sweep."""

    def request(self, method, url, *args, **kwargs):
        response = super().request(method, url, *args, **kwargs)
        COLLECTED.responses.append(
            (method, str(url), response.status_code, repr(dict(response.headers)), response.text)
        )
        return response


def _find_leaks():
    """Return list of (where, secret) for every planted secret found anywhere."""
    hits = []
    haystacks = {
        "log output": "\n".join(COLLECTED.logs),
        "stdout": "\n".join(COLLECTED.stdout),
        "stderr": "\n".join(COLLECTED.stderr),
        "api response bodies": "\n".join(r[4] for r in COLLECTED.responses),
        "api response headers": "\n".join(r[3] for r in COLLECTED.responses),
    }
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT ciphertext, provider, last_test_status FROM provider_keys")).fetchall()
        haystacks["provider_keys table (raw)"] = "\n".join(" ".join(str(c) for c in r) for r in rows)
    except Exception as exc:  # table missing is itself a failure we want to see
        haystacks["provider_keys table (raw)"] = f"<could not read table: {exc}>"
    for where, blob in haystacks.items():
        for secret in PLANTED_SECRETS:
            if secret in blob:
                hits.append((where, secret))
    return hits


def leak_report():
    return _find_leaks(), {
        "log_records": len(COLLECTED.logs),
        "stdout_chunks": len(COLLECTED.stdout),
        "stderr_chunks": len(COLLECTED.stderr),
        "api_responses": len(COLLECTED.responses),
    }


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.capstdout:
        COLLECTED.stdout.append(report.capstdout)
    if report.capstderr:
        COLLECTED.stderr.append(report.capstderr)


def pytest_sessionfinish(session, exitstatus):
    hits, counts = leak_report()
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    if hits:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        if tr:
            tr.write_sep("=", "KEY LEAK DETECTED", red=True, bold=True)
            for where, secret in hits:
                tr.write_line(f"  planted secret {secret[:18]}… found in {where}", red=True)
    elif tr:
        tr.write_sep(
            "-",
            "key leak sweep: no planted secret in %(log_records)d log records, %(stdout_chunks)d stdout / "
            "%(stderr_chunks)d stderr chunks, %(api_responses)d API responses, or the provider_keys table"
            % counts,
        )


# ---------------------------------------------------------------------------
# Standard fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Ensure tables exist before tests run."""
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup test users after all tests
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM provider_keys WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@test.autotube.com')"))
            conn.execute(text("DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@test.autotube.com')"))
            conn.execute(text("DELETE FROM job_logs WHERE job_id IN (SELECT id FROM jobs WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@test.autotube.com'))"))
            conn.execute(text("DELETE FROM jobs WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@test.autotube.com')"))
            conn.execute(text("DELETE FROM users WHERE email LIKE '%@test.autotube.com'"))
            conn.commit()
    except Exception:
        pass  # Don't fail teardown


@pytest.fixture(scope="function", autouse=True)
def reset_rate_limiters():
    """The in-memory per-IP limiters (10 auth req/min) would otherwise trip mid-suite,
    since every test talks to the app from the same TestClient address."""
    from app import middleware
    for limiter in (middleware.general_limiter, middleware.auth_limiter, middleware.job_limiter):
        with limiter.lock:
            limiter.requests.clear()
    yield


@pytest.fixture(scope="module")
def client():
    """Provides a TestClient for making HTTP requests to the FastAPI app."""
    with RecordingTestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session():
    """Provides a fresh DB session per test function."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


TEST_PASSWORD = "SecurePass123!"


def register_and_login(client, prefix: str) -> tuple[str, dict]:
    """Create a throwaway user; return its email and an Authorization header."""
    email = f"{prefix}_{uuid.uuid4().hex[:8]}@test.autotube.com"
    client.post("/auth/register", json={"email": email, "password": TEST_PASSWORD, "full_name": prefix})
    res = client.post("/auth/login", data={"username": email, "password": TEST_PASSWORD})
    return email, {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture(scope="session")
def vault_private_key() -> str:
    """The run's throwaway private key — for the decrypt tests only."""
    return TEST_VAULT_PRIVATE_KEY_B64
