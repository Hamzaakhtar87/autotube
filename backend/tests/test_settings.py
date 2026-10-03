"""
SETTINGS & BILLING API UNIT TESTS
Tests: Config status, Subscription status
"""
import pytest
import uuid

UNIQUE = uuid.uuid4().hex[:8]


def _register_and_login(client, prefix):
    """Helper: Register a user and return auth headers."""
    user = {
        "email": f"{prefix}_{UNIQUE}@test.autotube.com",
        "password": "SecurePass123!",
        "full_name": f"{prefix.title()} Test User"
    }
    client.post("/auth/register", json=user)
    res = client.post("/auth/login", data={
        "username": user["email"],
        "password": user["password"]
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestSettingsAPI:
    """Test settings/config endpoints."""

    @pytest.fixture(autouse=True)
    def setup_user(self, client):
        self.headers = _register_and_login(client, "settings")

    def test_config_status(self, client):
        """Should return config status."""
        res = client.get("/config/status", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert "has_client_secrets" in data
        assert "has_credentials" in data

    def test_config_status_without_auth(self, client):
        """Should reject config status without auth."""
        res = client.get("/config/status")
        assert res.status_code in [401, 403]

    def test_legacy_config_keys_route_is_gone(self, client):
        """POST /config/keys (unauthenticated, wrote keys into os.environ) was removed in Phase 2."""
        res = client.post("/config/keys", json={"pexels_key": "x", "gemini_key": "y"}, headers=self.headers)
        assert res.status_code in (404, 405)


class TestUploadSecrets:
    """POST /config/secrets writes the app-wide Google client_secrets.json: admin only."""

    @pytest.fixture(autouse=True)
    def setup_users(self, client, tmp_path, monkeypatch):
        from app.api import settings as settings_module
        from app.models.models import User
        from tests.conftest import TestingSessionLocal

        self.secrets_file = tmp_path / "client_secrets.json"
        monkeypatch.setattr(settings_module, "SECRETS_FILE", str(self.secrets_file))
        self.user = _register_and_login(client, "secrets_user")
        admin_email = f"secrets_admin_{UNIQUE}@test.autotube.com"
        client.post("/auth/register", json={"email": admin_email, "password": "SecurePass123!", "full_name": "Secrets Admin"})
        res = client.post("/auth/login", data={"username": admin_email, "password": "SecurePass123!"})
        self.admin = {"Authorization": f"Bearer {res.json()['access_token']}"}
        db = TestingSessionLocal()
        try:
            db.query(User).filter(User.email == admin_email).update({"is_admin": True})
            db.commit()
        finally:
            db.close()

    def test_rejects_unauthenticated(self, client):
        res = client.post("/config/secrets", json={"web": {}})
        assert res.status_code in [401, 403]
        assert not self.secrets_file.exists()

    def test_rejects_regular_user(self, client):
        res = client.post("/config/secrets", json={"web": {}}, headers=self.user)
        assert res.status_code == 403
        assert not self.secrets_file.exists()

    def test_admin_bad_body_gets_fixed_message_not_exception_text(self, client):
        res = client.post("/config/secrets", json={"nothing": True}, headers=self.admin)
        assert res.status_code == 400
        assert res.json()["detail"] == "Invalid client_secrets.json format"
        assert not self.secrets_file.exists()

    def test_admin_can_upload(self, client):
        res = client.post("/config/secrets", json={"web": {"client_id": "x"}}, headers=self.admin)
        assert res.status_code == 200
        import json
        assert json.loads(self.secrets_file.read_text()) == {"web": {"client_id": "x"}}


class TestBillingAPI:
    """Test billing/subscription endpoints."""

    @pytest.fixture(autouse=True)
    def setup_user(self, client):
        self.headers = _register_and_login(client, "billing")

    def test_get_subscription(self, client):
        """Should return subscription status for free user."""
        res = client.get("/billing/subscription", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data["tier"] == "free"
        assert "is_active" in data

    def test_subscription_without_auth(self, client):
        """Should reject subscription query without auth."""
        res = client.get("/billing/subscription")
        assert res.status_code in [401, 403]

    def test_checkout_without_auth(self, client):
        """Should reject checkout creation without auth."""
        res = client.post("/billing/create-checkout-session", json={"tier": "pro"})
        assert res.status_code in [401, 403]
