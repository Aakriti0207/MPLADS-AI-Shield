"""
Phase 2 tests: JWT protection on the projects/dashboard/alerts routers,
and that public routes remain public.

Uses the same fixtures as test_auth.py (client, registered_user,
auth_headers) from conftest.py. Since the test DB is empty (no seeded
Project rows), "successful response" for a valid-JWT request means a
200 with an empty/zero-valued body, not necessarily non-empty data --
that's expected and correct for these tests, which are about the auth
gate, not the business data.
"""


def test_projects_list_without_jwt_returns_401(client):
    resp = client.get("/projects")
    assert resp.status_code == 401


def test_projects_list_with_valid_jwt_returns_200(client, auth_headers):
    resp = client.get("/projects", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []  # no projects seeded in the test DB


def test_projects_detail_without_jwt_returns_401(client):
    resp = client.get("/projects/SOME-ID")
    assert resp.status_code == 401


def test_dashboard_stats_without_jwt_returns_401(client):
    resp = client.get("/dashboard/stats")
    assert resp.status_code == 401


def test_dashboard_stats_with_valid_jwt_returns_200(client, auth_headers):
    resp = client.get("/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total_projects"] == 0


def test_alerts_list_without_jwt_returns_401(client):
    resp = client.get("/alerts")
    assert resp.status_code == 401


def test_alerts_list_with_valid_jwt_returns_200(client, auth_headers):
    resp = client.get("/alerts", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_protected_routes_reject_invalid_jwt(client):
    headers = {"Authorization": "Bearer not-a-real-token"}
    assert client.get("/projects", headers=headers).status_code == 401
    assert client.get("/dashboard/stats", headers=headers).status_code == 401
    assert client.get("/alerts", headers=headers).status_code == 401


def test_protected_routes_reject_inactive_user(client, db_session, auth_headers, registered_user):
    from app.models import User

    user = db_session.query(User).filter(User.email == registered_user["email"]).first()
    user.is_active = False
    db_session.commit()

    # auth_headers was issued while the user was still active -- the
    # token itself is still validly signed and unexpired, so this
    # exercises get_current_user's is_active re-check against the DB,
    # not token expiry.
    assert client.get("/projects", headers=auth_headers).status_code == 401
    assert client.get("/dashboard/stats", headers=auth_headers).status_code == 401
    assert client.get("/alerts", headers=auth_headers).status_code == 401


def test_root_health_endpoint_is_public(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_register_and_login_remain_public(client):
    resp = client.post(
        "/auth/register",
        json={"email": "phase2.check@example.gov.in", "password": "SecurePass123", "role": "Administrator"},
    )
    assert resp.status_code == 201

    resp = client.post(
        "/auth/login",
        json={"email": "phase2.check@example.gov.in", "password": "SecurePass123"},
    )
    assert resp.status_code == 200


def test_openapi_marks_protected_routes_with_bearer_security(client):
    """Swagger's lock icon comes from the OpenAPI schema listing a
    security requirement on the operation -- verify it's present for
    protected routes and absent for public ones."""
    schema = client.get("/openapi.json").json()

    def has_bearer_security(path: str, method: str) -> bool:
        op = schema["paths"][path][method]
        return bool(op.get("security"))

    assert has_bearer_security("/projects", "get") is True
    assert has_bearer_security("/dashboard/stats", "get") is True
    assert has_bearer_security("/alerts", "get") is True
    assert has_bearer_security("/auth/me", "get") is True

    assert has_bearer_security("/auth/login", "post") is False
    assert has_bearer_security("/auth/register", "post") is False