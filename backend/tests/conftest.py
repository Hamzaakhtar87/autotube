"""
Test Configuration
Uses a separate test database to avoid polluting production data.
Connects to the Docker Postgres on localhost:5440.
"""
import pytest
import os
import sys

# Add backend to path so 'app' module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Override DATABASE_URL BEFORE any app imports
os.environ["DATABASE_URL"] = "postgresql://autotube:autotube_secret@127.0.0.1:5440/autotube_db"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db import Base, get_db

# Test database — same Postgres server but isolated via transactions
TEST_DATABASE_URL = "postgresql://autotube:autotube_secret@127.0.0.1:5440/autotube_db"

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Ensure tables exist before tests run."""
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup test users after all tests
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM refresh_tokens WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@test.autotube.com')"))
            conn.execute(text("DELETE FROM job_logs WHERE job_id IN (SELECT id FROM jobs WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@test.autotube.com'))"))
            conn.execute(text("DELETE FROM jobs WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@test.autotube.com')"))
            conn.execute(text("DELETE FROM users WHERE email LIKE '%@test.autotube.com'"))
            conn.commit()
    except Exception:
        pass  # Don't fail teardown


@pytest.fixture(scope="module")
def client():
    """Provides a TestClient for making HTTP requests to the FastAPI app."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session():
    """Provides a fresh DB session per test function."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
