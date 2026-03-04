"""
JOBS API UNIT TESTS
Tests: Job creation, listing, detail view, usage quota
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock

UNIQUE = uuid.uuid4().hex[:8]
JOB_USER = {
    "email": f"jobuser_{UNIQUE}@test.autotube.com",
    "password": "SecurePass123!",
    "full_name": "Job Test User"
}


class TestJobsAPI:
    """Test video generation job endpoints."""

    @pytest.fixture(autouse=True)
    def setup_user(self, client):
        """Register and login a test user for job tests."""
        client.post("/auth/register", json=JOB_USER)
        res = client.post("/auth/login", data={
            "username": JOB_USER["email"],
            "password": JOB_USER["password"]
        })
        self.token = res.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @patch("app.api.jobs.run_batch_task")
    def test_create_job(self, mock_task, client):
        """Should create a new job."""
        mock_task.delay.return_value = MagicMock(id="mock-celery-task-id")
        res = client.post("/jobs", json={
            "test_mode": True,
            "videos_count": 1
        }, headers=self.headers)
        assert res.status_code == 200, f"Job create failed: {res.text}"
        data = res.json()
        assert data["status"] == "pending"
        assert "id" in data
        mock_task.delay.assert_called_once()

    def test_list_jobs(self, client):
        """Should list user's jobs."""
        res = client.get("/jobs", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

    @patch("app.api.jobs.run_batch_task")
    def test_get_job_detail(self, mock_task, client):
        """Should get details for a specific job."""
        mock_task.delay.return_value = MagicMock(id="mock-celery-task-id")
        create_res = client.post("/jobs", json={
            "test_mode": True,
            "videos_count": 1
        }, headers=self.headers)
        job_id = create_res.json()["id"]

        res = client.get(f"/jobs/{job_id}", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == job_id
        assert "logs" in data

    def test_get_nonexistent_job(self, client):
        """Should return 404 for non-existent job."""
        res = client.get("/jobs/99999", headers=self.headers)
        assert res.status_code == 404

    def test_create_job_without_auth(self, client):
        """Should reject job creation without auth."""
        res = client.post("/jobs", json={"test_mode": True, "videos_count": 1})
        assert res.status_code in [401, 403]


class TestUsageAPI:
    """Test usage/quota endpoints."""

    @pytest.fixture(autouse=True)
    def setup_user(self, client):
        """Register and login a test user."""
        usage_user = {
            "email": f"usage_{UNIQUE}@test.autotube.com",
            "password": "SecurePass123!",
            "full_name": "Usage Test User"
        }
        client.post("/auth/register", json=usage_user)
        res = client.post("/auth/login", data={
            "username": usage_user["email"],
            "password": usage_user["password"]
        })
        self.token = res.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_get_usage(self, client):
        """Should return usage stats."""
        res = client.get("/usage", headers=self.headers)
        assert res.status_code == 200
        data = res.json()
        assert "videos_generated_this_month" in data
        assert "videos_limit" in data
        assert "subscription_tier" in data
        assert data["subscription_tier"] == "free"

    def test_usage_without_auth(self, client):
        """Should reject usage query without auth."""
        res = client.get("/usage")
        assert res.status_code in [401, 403]
