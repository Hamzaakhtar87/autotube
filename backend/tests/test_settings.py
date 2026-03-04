"""
SETTINGS & BILLING API UNIT TESTS
Tests: Config status, API key update, Subscription status
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

    def test_update_api_keys(self, client):
        """Should accept API key updates."""
        res = client.post("/config/keys", json={
            "openai_key": "sk-test-key",
            "pexels_key": "test-pexels-key",
            "gemini_key": "test-gemini-key"
        })
        assert res.status_code == 200
        assert res.json()["status"] == "updated"


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
