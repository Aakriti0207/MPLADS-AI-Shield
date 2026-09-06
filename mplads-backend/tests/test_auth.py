"""
Backend authentication tests (Phase 1 scope): register, login, and
/auth/me. Protected application routes (projects/dashboard/alerts) are
tested separately once Phase 3 adds protection to them.

Uses an in-memory SQLite DB per test (see conftest.py) so these run
without a live PostgreSQL instance, matching the project's own
documented SQLite-for-testing approach.
"""

from datetime import datetime, timedelta, timezone

import jwt

from app.auth import JWT_ALGORITHM, JWT_SECRET_KEY


# --- Registration -------------------------------------------------------

def test_register_new_user(client):
    resp = client.post(
        "/auth/register",
        json={
            "email": "new.user@example.gov.in",
            "password": "SecurePass123",
            "role": "State Nodal Officer",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new.user@example.gov.in"
    assert body["role"] == "State Nodal Officer"
    assert body["is_active"] is True
    # Never leak the hash.
    assert "password_hash" not in body
    assert "password" not in body


def test_register_duplicate_email_rejected(client, registered_user):
    resp = client.post(
        "/auth/register",
        json={
            "email": registered_user["email"],
            "password": "AnotherPass123",
            "role": "Administrator",
        },
    )
    assert resp.status_code == 400


def test_register_short_password_rejected(client):
    resp = client.post(
        "/auth/register",
        json={"email": "short.pw@example.gov.in", "password": "short", "role": "Administrator"},
    )
    assert resp.status_code == 422


def test_register_invalid_email_rejected(client):
    resp = client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": "SecurePass123", "role": "Administrator"},
    )
    assert resp.status_code == 422


# --- Login ---------------------------------------------------------------

def test_login_correct_credentials(client, registered_user):
    resp = client.post(
        "/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_incorrect_password(client, registered_user):
    resp = client.post(
        "/auth/login",
        json={"email": registered_user["email"], "password": "WrongPassword123"},
    )
    assert resp.status_code == 401


def test_login_nonexistent_email(client):
    resp = client.post(
        "/auth/login",
        json={"email": "nobody@example.gov.in", "password": "SecurePass123"},
    )
    assert resp.status_code == 401


def test_login_inactive_user_rejected(client, db_session, registered_user):
    from app.models import User

    user = db_session.query(User).filter(User.email == registered_user["email"]).first()
    user.is_active = False
    db_session.commit()

    resp = client.post(
        "/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert resp.status_code == 401


# --- /auth/me --------------------------------------------------------------

def test_me_with_valid_jwt(client, auth_headers, registered_user):
    resp = client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == registered_user["email"]
    assert "password_hash" not in body


def test_me_without_jwt(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_with_invalid_jwt(client):
    resp = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_me_with_expired_jwt(client, registered_user):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "1",
        "email": registered_user["email"],
        "role": registered_user["role"],
        "iat": now - timedelta(minutes=120),
        "exp": now - timedelta(minutes=60),
    }
    expired_token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


def test_me_with_jwt_for_nonexistent_user(client):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "999999",
        "email": "ghost@example.gov.in",
        "role": "Administrator",
        "iat": now,
        "exp": now + timedelta(minutes=60),
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


def test_register_and_login_endpoints_are_public(client):
    """/auth/register and /auth/login must not require a token themselves."""
    resp = client.post(
        "/auth/register",
        json={"email": "open.check@example.gov.in", "password": "SecurePass123", "role": "Administrator"},
    )
    assert resp.status_code == 201

    resp = client.post(
        "/auth/login",
        json={"email": "open.check@example.gov.in", "password": "SecurePass123"},
    )
    assert resp.status_code == 200