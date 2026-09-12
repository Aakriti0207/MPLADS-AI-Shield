"""
Phase 2 tests: role-based authorization.

Audit finding this phase is built on (see the Phase 2 handoff report):
the application already has a `role` column on `User` (a free-text
string, not a fixed enum -- see app/models.py) and an already-built
`require_role` dependency factory (app/auth.py) that was written "for
future role-based authorization" but had never been wired to any route
or exercised by a test. No endpoint in this application currently has a
genuinely privileged/admin-only operation to gate (every existing route
is either public, per test_protected_routes.py, or requires nothing
more than an authenticated active user, per test_project_api.py /
test_risk_and_dashboard.py / test_upload_analyze.py, etc.) -- so this
file does not invent one. Instead it:

  1. Exercises `require_role` directly as a unit (the standard way to
     test a FastAPI dependency factory without needing a real gated
     route), proving its 401-vs-403 semantics and its allow/deny
     behavior for both a privileged ("Administrator") and an ordinary
     role.
  2. Proves, end-to-end through the real app, that both an
     "Administrator" user and an ordinary-role user can use the
     existing authenticated read endpoints identically (there is no
     hidden distinction to find here -- this documents that fact).
  3. Locks down the real gap this phase exists to close: public
     registration can no longer be used to grant oneself the
     "Administrator" role, while every other self-chosen role title
     keeps working exactly as before.

Uses the same `client` / `registered_user` / `auth_headers` fixtures as
test_auth.py and test_protected_routes.py (see conftest.py) -- no new
test database or fixture architecture.
"""

import jwt
import pytest
from fastapi import HTTPException

from app.auth import (
    ADMIN_ROLE,
    DEFAULT_REGISTRATION_ROLE,
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    require_role,
    resolve_registration_role,
)
from app.models import User


def _fake_user(role: str) -> User:
    """A plain (non-persisted) User instance -- enough for require_role's
    check, which only reads `.role`."""
    return User(id=1, email="fixture@example.gov.in", password_hash="x", role=role, is_active=True)


# ---------------------------------------------------------------------------
# 1. require_role: unit-level authorization semantics
# ---------------------------------------------------------------------------


def test_require_role_allows_a_role_in_the_allow_list():
    dependency = require_role(ADMIN_ROLE)
    admin_user = _fake_user(ADMIN_ROLE)
    assert dependency(current_user=admin_user) is admin_user


def test_require_role_allows_any_of_several_roles():
    dependency = require_role(ADMIN_ROLE, "District Authority")
    ordinary_user = _fake_user("District Authority")
    assert dependency(current_user=ordinary_user) is ordinary_user


def test_require_role_rejects_a_role_not_in_the_allow_list_with_403():
    dependency = require_role(ADMIN_ROLE)
    ordinary_user = _fake_user("District Authority")
    with pytest.raises(HTTPException) as excinfo:
        dependency(current_user=ordinary_user)
    assert excinfo.value.status_code == 403


def test_require_role_rejects_an_unrelated_role_with_403():
    """Analyst-tier role rejected from an admin-only check -- proves
    require_role generalizes beyond just the two roles exercised above,
    without this application needing to invent a fixed role enum."""
    dependency = require_role(ADMIN_ROLE)
    other_user = _fake_user("State Nodal Officer")
    with pytest.raises(HTTPException) as excinfo:
        dependency(current_user=other_user)
    assert excinfo.value.status_code == 403


# ---------------------------------------------------------------------------
# 2. Existing authenticated endpoints: identical access across roles
# ---------------------------------------------------------------------------
#
# Every currently authenticated route (projects/dashboard/alerts/
# analytics/upload) requires only Depends(get_current_user) -- no role
# distinction exists among them today (see the Phase 2 report for why
# inventing one here would be pure self-reported-title theater, since
# any non-Administrator title is freely self-selectable at registration
# regardless). These two tests document that both an Administrator and
# an ordinary-role account get the same (successful) access.


def _register_and_login(client, email: str, password: str, role: str) -> dict:
    resp = client.post("/auth/register", json={"email": email, "password": password, "role": role})
    assert resp.status_code == 201, resp.text
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_role_user_can_access_authenticated_read_endpoints(client):
    headers = _register_and_login(client, "admin.rbac@example.gov.in", "SecurePass123", "Administrator")
    assert client.get("/dashboard/stats", headers=headers).status_code == 200
    assert client.get("/projects", headers=headers).status_code == 200
    assert client.get("/alerts", headers=headers).status_code == 200


def test_ordinary_role_user_can_access_the_same_authenticated_read_endpoints(client):
    headers = _register_and_login(client, "district.rbac@example.gov.in", "SecurePass123", "District Authority")
    assert client.get("/dashboard/stats", headers=headers).status_code == 200
    assert client.get("/projects", headers=headers).status_code == 200
    assert client.get("/alerts", headers=headers).status_code == 200


# ---------------------------------------------------------------------------
# 3. Registration privilege-escalation
# ---------------------------------------------------------------------------


def test_resolve_registration_role_downgrades_administrator():
    assert resolve_registration_role("Administrator") == DEFAULT_REGISTRATION_ROLE


@pytest.mark.parametrize("submitted", ["administrator", "ADMIN", "Admin", " Administrator "])
def test_resolve_registration_role_downgrades_case_and_whitespace_variants(submitted):
    assert resolve_registration_role(submitted) == DEFAULT_REGISTRATION_ROLE


def test_resolve_registration_role_preserves_ordinary_titles():
    assert resolve_registration_role("District Authority") == "District Authority"
    assert resolve_registration_role("State Nodal Officer") == "State Nodal Officer"


def test_public_registration_cannot_create_an_administrator_account(client):
    resp = client.post(
        "/auth/register",
        json={"email": "escalation.attempt@example.gov.in", "password": "SecurePass123", "role": "Administrator"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == DEFAULT_REGISTRATION_ROLE
    assert resp.json()["role"] != ADMIN_ROLE


def test_public_registration_cannot_create_an_administrator_account_via_case_variant(client):
    resp = client.post(
        "/auth/register",
        json={"email": "escalation.variant@example.gov.in", "password": "SecurePass123", "role": "admin"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == DEFAULT_REGISTRATION_ROLE


def test_newly_registered_user_with_ordinary_role_keeps_that_role(client):
    """Confirms the downgrade is scoped to the privileged label only --
    registration is not silently turned into a fixed-default-for-everyone
    scheme (that would break test_auth.py::test_register_new_user)."""
    resp = client.post(
        "/auth/register",
        json={"email": "ordinary.role@example.gov.in", "password": "SecurePass123", "role": "State Nodal Officer"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "State Nodal Officer"


def test_administrator_account_cannot_actually_log_in_and_use_admin_privilege_after_registering(client):
    """End-to-end: register attempting Administrator, log in, and prove
    the issued JWT/DB role is the downgraded one, not Administrator."""
    email, password = "escalation.e2e@example.gov.in", "SecurePass123"
    client.post("/auth/register", json={"email": email, "password": password, "role": "Administrator"})
    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    decoded = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    assert decoded["role"] == DEFAULT_REGISTRATION_ROLE


# ---------------------------------------------------------------------------
# 4. /auth/me reflects the actual role
# ---------------------------------------------------------------------------


def test_auth_me_returns_the_downgraded_role_after_an_escalation_attempt(client):
    email, password = "me.rbac@example.gov.in", "SecurePass123"
    client.post("/auth/register", json={"email": email, "password": password, "role": "Administrator"})
    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    me_resp = client.get("/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == DEFAULT_REGISTRATION_ROLE


def test_auth_me_returns_an_ordinary_role_unchanged(client):
    email, password = "me.ordinary.rbac@example.gov.in", "SecurePass123"
    client.post("/auth/register", json={"email": email, "password": password, "role": "State Nodal Officer"})
    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    me_resp = client.get("/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "State Nodal Officer"


# ---------------------------------------------------------------------------
# 5. Role changes take effect from the database, not a stale JWT claim
# ---------------------------------------------------------------------------


def test_role_check_reflects_current_database_role_not_the_original_jwt_claim(client, db_session):
    """A user's token was issued while they held an ordinary role; if an
    operator promotes them in the database afterwards, the *next*
    request must see the new role -- get_current_user re-reads the DB
    row every time rather than trusting the JWT's original role claim."""
    email, password = "promote.rbac@example.gov.in", "SecurePass123"
    client.post("/auth/register", json={"email": email, "password": password, "role": "District Authority"})
    login_resp = client.post("/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}
    token = login_resp.json()["access_token"]

    # The token itself still carries the old role claim...
    original_claim = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])["role"]
    assert original_claim == "District Authority"

    # ...but promote the user directly in the DB, simulating an
    # operator-managed role change with no new token issued.
    user = db_session.query(User).filter(User.email == email).first()
    user.role = ADMIN_ROLE
    db_session.commit()

    me_resp = client.get("/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == ADMIN_ROLE  # reflects the DB, not the stale JWT claim


# ---------------------------------------------------------------------------
# 6. Regression: unauthenticated/invalid-token behavior is unchanged
# ---------------------------------------------------------------------------


def test_missing_token_still_returns_401_not_403(client):
    resp = client.get("/dashboard/stats")
    assert resp.status_code == 401


def test_invalid_token_still_returns_401_not_403(client):
    resp = client.get("/dashboard/stats", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401