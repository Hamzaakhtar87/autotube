"""
AUTH API UNIT TESTS
Tests: Registration, Login, JWT Token, Protected Routes, Edge Cases
"""
import pytest
import uuid


# Generate unique email per test run to avoid conflicts
UNIQUE = uuid.uuid4().hex[:8]
TEST_USER = {
    "email": f"user_{UNIQUE}@test.autotube.com",
    "password": "SecurePass123!",
    "full_name": "Test User"
}

# Module-level token storage
_access_token = None


def _login(client):
    """Helper: login and return access token."""
    res = client.post("/auth/login", data={
        "username": TEST_USER["email"],
        "password": TEST_USER["password"]
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    return res.json()["access_token"]


class TestRegistration:
    """Test user registration flow."""

    def test_register_success(self, client):
        """Should create a new user and return user data."""
        global _access_token
        res = client.post("/auth/register", json=TEST_USER)
        assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
        data = res.json()
        assert data["email"] == TEST_USER["email"]
        assert data["subscription_tier"] == "free"
        assert "id" in data
        # Login to get token for later tests
        _access_token = _login(client)

    def test_register_duplicate_email(self, client):
        """Should reject duplicate email."""
        res = client.post("/auth/register", json=TEST_USER)
        assert res.status_code == 400
        assert "already" in res.json()["detail"].lower()

    def test_register_short_password(self, client):
        """Should reject password < 8 characters."""
        res = client.post("/auth/register", json={
            "email": f"short_{UNIQUE}@test.autotube.com",
            "password": "abc",
            "full_name": "Short Pass"
        })
        assert res.status_code == 400
        assert "8 characters" in res.json()["detail"]

    def test_register_invalid_email(self, client):
        """Should reject invalid email format."""
        res = client.post("/auth/register", json={
            "email": "not-an-email",
            "password": "ValidPass123",
            "full_name": "Bad Email"
        })
        assert res.status_code == 422  # Pydantic validation error


class TestLogin:
    """Test user login flow."""

    def test_login_success(self, client):
        """Should return access_token on valid credentials."""
        res = client.post("/auth/login", data={
            "username": TEST_USER["email"],
            "password": TEST_USER["password"]
        })
        assert res.status_code == 200, f"Login failed: {res.text}"
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        """Should reject wrong password."""
        res = client.post("/auth/login", data={
            "username": TEST_USER["email"],
            "password": "WrongPassword999"
        })
        assert res.status_code == 401

    def test_login_nonexistent_user(self, client):
        """Should reject login for non-existent user."""
        res = client.post("/auth/login", data={
            "username": "ghost@nobody.com",
            "password": "doesntmatter"
        })
        assert res.status_code == 401


class TestProtectedRoutes:
    """Test JWT-protected endpoints."""

    def test_me_with_valid_token(self, client):
        """Should return user profile with valid token."""
        global _access_token
        assert _access_token, "No token available — registration test must run first"
        res = client.get("/auth/me", headers={"Authorization": f"Bearer {_access_token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == TEST_USER["email"]
        assert data["full_name"] == TEST_USER["full_name"]

    def test_me_without_token(self, client):
        """Should return 401 without token."""
        res = client.get("/auth/me")
        assert res.status_code in [401, 403]

    def test_me_with_invalid_token(self, client):
        """Should return 401 with garbage token."""
        res = client.get("/auth/me", headers={"Authorization": "Bearer fake.garbage.token"})
        assert res.status_code == 401

    def test_update_profile(self, client):
        """Should update user name."""
        global _access_token
        res = client.patch("/auth/me",
            headers={"Authorization": f"Bearer {_access_token}"},
            json={"full_name": "Updated Name"}
        )
        assert res.status_code == 200
        assert res.json()["full_name"] == "Updated Name"


class TestHealthCheck:
    """Test basic API availability."""

    def test_root_health(self, client):
        """Root endpoint should return ok status."""
        res = client.get("/")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"
