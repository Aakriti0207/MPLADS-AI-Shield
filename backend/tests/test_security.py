"""
Phase 6 tests: CORS configuration, rate limiting, security headers, and
the global unhandled-exception handler.

Everything Step 15 of the Phase 6 spec already asked for that existed
BEFORE this phase (expired/invalid/nonexistent-user JWT rejection,
inactive-user rejection, password never returned, root endpoint public,
malformed registration input rejected, protected routes reject missing
auth) is already covered by test_auth.py and test_protected_routes.py --
not duplicated here. This file covers only what's new in Phase 6.
"""

import pytest

from app.main import _resolve_cors_origins


# --- CORS -----------------------------------------------------------------

def test_cors_allows_configured_origin(client):
    resp = client.options(
        "/projects",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unlisted_origin(client):
    resp = client.options(
        "/projects",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in {k.lower() for k in resp.headers.keys()}


def test_resolve_cors_origins_defaults_to_local_dev_when_unset(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    origins = _resolve_cors_origins()
    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins


def test_resolve_cors_origins_parses_comma_separated_list(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", " https://a.example.com ,https://b.example.com")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    origins = _resolve_cors_origins()
    assert origins == ["https://a.example.com", "https://b.example.com"]


def test_resolve_cors_origins_required_in_production(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(RuntimeError):
        _resolve_cors_origins()
    monkeypatch.delenv("ENVIRONMENT", raising=False)


def test_resolve_cors_origins_accepts_explicit_value_in_production(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://prod.example.com")
    monkeypatch.setenv("ENVIRONMENT", "production")
    origins = _resolve_cors_origins()
    assert origins == ["https://prod.example.com"]
    monkeypatch.delenv("ENVIRONMENT", raising=False)


# --- Rate limiting ----------------------------------------------------------

def test_login_is_rate_limited_after_repeated_attempts(client, registered_user):
    # The fixture's own login call (auth_headers isn't used here, so no
    # extra call) plus 5 more should exhaust the 5-per-60s login limit.
    for _ in range(5):
        resp = client.post(
            "/auth/login",
            json={"email": registered_user["email"], "password": "wrong-password"},
        )
        assert resp.status_code == 401

    resp = client.post(
        "/auth/login",
        json={"email": registered_user["email"], "password": "wrong-password"},
    )
    assert resp.status_code == 429
    assert "retry-after" in {k.lower() for k in resp.headers.keys()}


def test_register_is_rate_limited_after_repeated_attempts(client):
    for i in range(5):
        client.post(
            "/auth/register",
            json={"email": f"ratelimit{i}@example.gov.in", "password": "SecurePass123", "role": "Administrator"},
        )

    resp = client.post(
        "/auth/register",
        json={"email": "one.more@example.gov.in", "password": "SecurePass123", "role": "Administrator"},
    )
    assert resp.status_code == 429


def test_rate_limit_is_independent_per_endpoint(client, registered_user):
    """Exhausting the register limit must not affect the (separately
    tracked) login limit."""
    for i in range(5):
        client.post(
            "/auth/register",
            json={"email": f"other{i}@example.gov.in", "password": "SecurePass123", "role": "Administrator"},
        )

    resp = client.post(
        "/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert resp.status_code == 200


# --- Security headers -------------------------------------------------------

def test_security_headers_present_on_response(client, auth_headers):
    resp = client.get("/projects", headers=auth_headers)
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "no-referrer"
    assert resp.headers.get("cache-control") == "no-store"


def test_security_headers_present_on_public_root(client):
    resp = client.get("/")
    assert resp.headers.get("x-content-type-options") == "nosniff"


# --- Global unhandled-exception handler -------------------------------------

def test_unhandled_exception_returns_generic_500(client, auth_headers):
    """
    NOTE: this uses a fresh TestClient with raise_server_exceptions=False.
    Starlette's ServerErrorMiddleware -- which is what actually invokes
    our @app.exception_handler(Exception) -- sends the handler's response
    to the client AND re-raises the original exception afterward (by
    design, so ASGI servers/dev tooling can log it); TestClient's default
    raise_server_exceptions=True surfaces that re-raise as a Python
    exception in the test itself instead of letting us inspect the HTTP
    response. A real client (browser, curl, the frontend) only ever sees
    the HTTP response below, never the exception -- this is a TestClient
    testing detail, not a gap in the handler.
    """
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    def _broken_get_db():
        raise RuntimeError("simulated internal failure with a secret path /etc/shadow")
        yield  # pragma: no cover -- unreachable, keeps this a generator

    app.dependency_overrides[get_db] = _broken_get_db
    with TestClient(app, raise_server_exceptions=False) as unsafe_client:
        resp = unsafe_client.get("/projects", headers=auth_headers)

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error."}
    # The body must never leak the exception message, a file path, or a
    # traceback -- only the generic detail above.
    assert "secret" not in resp.text
    assert "/etc/shadow" not in resp.text
    assert "RuntimeError" not in resp.text
    assert "Traceback" not in resp.text


def test_existing_endpoints_still_work_after_phase6_hardening(client, auth_headers):
    """Backward-compatibility spot check across every router."""
    assert client.get("/").status_code == 200
    assert client.get("/projects", headers=auth_headers).status_code == 200
    assert client.get("/dashboard/stats", headers=auth_headers).status_code == 200
    assert client.get("/alerts", headers=auth_headers).status_code == 200
    assert client.get("/analytics", headers=auth_headers).status_code == 200