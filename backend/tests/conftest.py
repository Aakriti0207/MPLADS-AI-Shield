"""
Shared pytest fixtures for the auth test suite.

Uses an in-memory SQLite database instead of PostgreSQL for tests --
consistent with the "SQLite used for local testing" approach already
anticipated by app/schema_migration.py's docstring. Production still
runs on PostgreSQL via DATABASE_URL; nothing here changes that.

Environment variables (DATABASE_URL, JWT_SECRET_KEY, ...) are set
*before* importing any `app.*` module, since app/database.py and
app/auth.py read them at import time and raise if missing.
"""

import os

import pytest

# Must be set before importing app.database / app.auth.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test_unused")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only-not-for-real-use")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.rate_limit import reset_all as _reset_rate_limits

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """
    Phase 6: reset every in-memory rate limiter (app/rate_limit.py)
    before each test. Without this, the limiters are module-level
    singletons that persist for the whole pytest process, so an early
    test's calls to /auth/register or /auth/login would count toward
    the same limit as every later test's calls, eventually tripping a
    429 in tests that have nothing to do with rate limiting. This has
    no effect on the running application -- reset_all() is test-only.
    """
    _reset_rate_limits()
    yield


@pytest.fixture()
def db_session():
    """A fresh in-memory SQLite DB + session for each test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """A TestClient with get_db overridden to use the SQLite test session."""

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def registered_user(client):
    """Register a standard test user and return (email, password, role)."""
    email = "test.user@example.gov.in"
    password = "SecurePass123"
    role = "District Authority"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "role": role},
    )
    assert resp.status_code == 201, resp.text
    return {"email": email, "password": password, "role": role, "body": resp.json()}


@pytest.fixture()
def auth_headers(client, registered_user):
    """Log in as `registered_user` and return Authorization headers."""
    resp = client.post(
        "/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}