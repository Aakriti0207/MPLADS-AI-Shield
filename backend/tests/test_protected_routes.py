"""
JWT protection tests for projects/dashboard/alerts routers,
and verification that public routes remain public.

The current production API uses the canonical production datasets
rather than the test database as the source of truth.
"""


def test_projects_list_without_jwt_returns_401(client):
    resp = client.get("/projects")
    assert resp.status_code == 401


def test_projects_list_with_valid_jwt_returns_200(client, auth_headers):
    resp = client.get("/projects", headers=auth_headers)

    assert resp.status_code == 200

    data = resp.json()

    assert isinstance(data, list)
    assert len(data) > 0
    assert len(data) <= 50

    for project in data:
        assert "project_id" in project


def test_projects_detail_without_jwt_returns_401(client):
    resp = client.get("/projects/SOME-ID")
    assert resp.status_code == 401


def test_dashboard_stats_without_jwt_returns_401(client):
    resp = client.get("/dashboard/stats")
    assert resp.status_code == 401


def test_dashboard_stats_with_valid_jwt_returns_200(client, auth_headers):
    resp = client.get("/dashboard/stats", headers=auth_headers)

    assert resp.status_code == 200

    data = resp.json()

    assert data["total_projects"] == 43863


def test_alerts_list_without_jwt_returns_401(client):
    resp = client.get("/alerts")
    assert resp.status_code == 401


def test_alerts_list_with_valid_jwt_returns_200(client, auth_headers):
    resp = client.get("/alerts", headers=auth_headers)

    assert resp.status_code == 200

    data = resp.json()

    assert isinstance(data, list)


def test_protected_routes_reject_invalid_jwt(client):
    headers = {"Authorization": "Bearer not-a-real-token"}

    assert client.get(
        "/projects",
        headers=headers,
    ).status_code == 401

    assert client.get(
        "/dashboard/stats",
        headers=headers,
    ).status_code == 401

    assert client.get(
        "/alerts",
        headers=headers,
    ).status_code == 401


def test_protected_routes_reject_inactive_user(
    client,
    db_session,
    auth_headers,
    registered_user,
):
    from app.models import User

    user = (
        db_session.query(User)
        .filter(User.email == registered_user["email"])
        .first()
    )

    user.is_active = False
    db_session.commit()

    # Token was issued while the user was active. The API must still
    # re-check the user's active status against the database.
    assert client.get(
        "/projects",
        headers=auth_headers,
    ).status_code == 401

    assert client.get(
        "/dashboard/stats",
        headers=auth_headers,
    ).status_code == 401

    assert client.get(
        "/alerts",
        headers=auth_headers,
    ).status_code == 401


def test_root_health_endpoint_is_public(client):
    resp = client.get("/")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_register_and_login_remain_public(client):
    resp = client.post(
        "/auth/register",
        json={
            "email": "phase2.check@example.gov.in",
            "password": "SecurePass123",
            "role": "Administrator",
        },
    )

    assert resp.status_code == 201

    resp = client.post(
        "/auth/login",
        json={
            "email": "phase2.check@example.gov.in",
            "password": "SecurePass123",
        },
    )

    assert resp.status_code == 200


def test_openapi_marks_protected_routes_with_bearer_security(client):
    """
    Swagger's lock icon comes from the OpenAPI operation containing
    a security requirement.
    """
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