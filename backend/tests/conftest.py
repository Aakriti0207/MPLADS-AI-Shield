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
def auth_headers(client, registered_user, db_session):
    """Log in as `registered_user` and return Authorization headers for a
    NATIONALLY-SCOPED session.

    Why the promotion happens here
    ------------------------------
    Before RBAC data-scoping existed, every authenticated account could
    read all 43,863 projects, so this fixture's session happened to see
    the whole dataset and the existing suite asserts exactly that (e.g.
    test_protected_routes.py's `total_projects == 43863`, and
    test_project_api.py / test_risk_and_dashboard.py / test_risk_fields.py
    reading arbitrary project IDs).

    That is no longer true for a jurisdictional account, and it should
    not be: the whole point of the change is that a District Authority
    account sees its own district. Those tests are not testing RBAC --
    they are testing the project/dashboard/risk/report CONTRACTS over the
    full dataset, which is a Ministry-scoped concern. So this fixture is
    promoted to the Ministry role (the same DB-promotion technique
    `admin_auth_headers` below already uses, and the same one
    test_rbac.py's role-change test relies on) and those suites keep
    exercising exactly what they were written to exercise, unmodified.

    Scoped behaviour is covered separately and explicitly by the
    `mp_auth_headers` / `state_auth_headers` / `district_auth_headers`
    fixtures below and by tests/test_rbac_scope.py.
    """
    from app.models import User

    resp = client.post(
        "/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]

    # get_current_user re-reads the role from the DB on every request, so
    # the already-issued token immediately reflects this.
    user = db_session.query(User).filter(User.email == registered_user["email"]).first()
    user.role = "Ministry"
    db_session.commit()

    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------
# RBAC fixtures: genuinely scoped accounts
# ---------------------------------------------------------------------
#
# These create real users with a real assigned jurisdiction, exactly the
# way an operator would provision one (registration never grants a
# jurisdiction -- see app/routes/auth.py). Tests that need to prove a
# scoped account CANNOT reach something use these.

def make_scoped_headers(
    client,
    db_session,
    *,
    email: str,
    role: str,
    scope_state=None,
    scope_district=None,
    scope_constituency=None,
    scope_mp_name=None,
    full_name=None,
):
    """Register an account, assign it a jurisdiction, return its headers."""
    from app.models import User

    # A cross-role test legitimately provisions more accounts than the
    # /auth/register rate limit allows in one window. The limiter is a
    # production brute-force deterrent, not the thing under test here, so
    # it is reset per provisioned account (test-only -- see
    # app/rate_limit.py's reset_all).
    _reset_rate_limits()

    password = "SecurePass123"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "role": role},
    )
    assert resp.status_code == 201, resp.text

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    user = db_session.query(User).filter(User.email == email).first()
    user.role = role
    user.full_name = full_name
    user.scope_state = scope_state
    user.scope_district = scope_district
    user.scope_constituency = scope_constituency
    user.scope_mp_name = scope_mp_name
    db_session.commit()

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_auth_headers(client, db_session):
    """Log in as a real Ministry/Admin user and return Authorization headers.

    `POST /auth/register` always silently downgrades a requested
    "Administrator" role to DEFAULT_REGISTRATION_ROLE (see
    resolve_registration_role / test_rbac.py) -- there is deliberately
    no way to self-register a privileged account. So, exactly like
    test_rbac.py's `test_role_check_reflects_current_database_role_...`,
    this registers+logs in an ordinary user first, then promotes that
    user directly in the DB (`user.role = ADMIN_ROLE`) before returning
    headers built from the already-issued token -- `get_current_user`
    re-reads `.role` from the DB on every request, so the existing
    token immediately reflects the promotion without a fresh login.

    Used by upload-analyze tests that need a genuinely Ministry/Admin
    caller now that `/upload-analyze` is role-gated (require_ministry_or_admin).
    """
    from app.auth import ADMIN_ROLE
    from app.models import User

    email, password = "upload.admin@example.gov.in", "SecurePass123"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "role": "District Authority"},
    )
    assert resp.status_code == 201, resp.text
    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]

    user = db_session.query(User).filter(User.email == email).first()
    user.role = ADMIN_ROLE
    db_session.commit()

    return {"Authorization": f"Bearer {token}"}