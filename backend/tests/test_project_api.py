"""
Phase 7 QA: GET /projects and GET /projects/{project_id} -- pagination
edge cases, deterministic ordering, and 404 behavior. Basic auth-gate
coverage for these routes already exists in test_protected_routes.py
and is not duplicated here.
"""

from decimal import Decimal

from app.models import Project


def _make_projects(db_session, count: int, prefix: str = "WS/PAGE"):
    for i in range(count):
        db_session.add(Project(project_id=f"{prefix}/{i:03d}", is_synthetic=True))
    db_session.commit()


# --- Pagination: valid behavior -------------------------------------------

def test_projects_list_default_pagination(client, db_session, auth_headers):
    _make_projects(db_session, 5)
    resp = client.get("/projects", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 5  # fewer than DEFAULT_LIMIT (50)


def test_projects_list_respects_limit(client, db_session, auth_headers):
    _make_projects(db_session, 10)
    resp = client.get("/projects?limit=3", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_projects_list_respects_skip(client, db_session, auth_headers):
    _make_projects(db_session, 5)
    all_ids = [p["project_id"] for p in client.get("/projects", headers=auth_headers).json()]

    skipped = client.get("/projects?skip=2", headers=auth_headers).json()
    assert [p["project_id"] for p in skipped] == all_ids[2:]


def test_projects_list_ordering_is_deterministic_across_pages(client, db_session, auth_headers):
    """Consecutive skip/limit pages must not overlap or skip rows --
    this is exactly what the explicit ORDER BY project_id in
    routes/projects.py exists to guarantee."""
    _make_projects(db_session, 12)

    page1 = client.get("/projects?skip=0&limit=5", headers=auth_headers).json()
    page2 = client.get("/projects?skip=5&limit=5", headers=auth_headers).json()
    page3 = client.get("/projects?skip=10&limit=5", headers=auth_headers).json()

    ids_seen = [p["project_id"] for p in page1 + page2 + page3]
    assert len(ids_seen) == len(set(ids_seen)) == 12  # no duplicates, no gaps
    assert ids_seen == sorted(ids_seen)  # matches the API's own documented order


def test_projects_list_empty_database_returns_empty_list(client, auth_headers):
    resp = client.get("/projects", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


# --- Pagination: invalid input is a controlled 422, never a crash --------

def test_projects_list_negative_skip_returns_422(client, auth_headers):
    resp = client.get("/projects?skip=-1", headers=auth_headers)
    assert resp.status_code == 422


def test_projects_list_zero_limit_returns_422(client, auth_headers):
    resp = client.get("/projects?limit=0", headers=auth_headers)
    assert resp.status_code == 422


def test_projects_list_negative_limit_returns_422(client, auth_headers):
    resp = client.get("/projects?limit=-5", headers=auth_headers)
    assert resp.status_code == 422


def test_projects_list_excessive_limit_returns_422(client, auth_headers):
    """MAX_LIMIT is 100 -- the API rejects a request for more than that
    rather than silently capping it, so callers aren't misled into
    thinking they got fewer rows than actually exist."""
    resp = client.get("/projects?limit=1000", headers=auth_headers)
    assert resp.status_code == 422


def test_projects_list_non_numeric_pagination_returns_422(client, auth_headers):
    resp = client.get("/projects?skip=abc", headers=auth_headers)
    assert resp.status_code == 422


# --- GET /projects/{project_id} --------------------------------------------

def test_project_detail_success_matches_schema_fields(client, db_session, auth_headers):
    db_session.add(Project(
        project_id="WS/DETAIL/1",
        state="Kerala",
        sanctioned_amount=Decimal("100000.00"),
        expenditure=Decimal("50000.00"),
        is_synthetic=True,
    ))
    db_session.commit()

    resp = client.get("/projects/WS%2FDETAIL%2F1", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] == "WS/DETAIL/1"
    assert body["state"] == "Kerala"
    assert float(body["sanctioned_amount"]) == 100000.0
    # Nullable fields that were never set must come back as null, never
    # a fabricated default.
    assert body["district"] is None
    assert body["risk_score"] is None
    assert body["physical_progress"] is None


def test_project_detail_nonexistent_id_returns_404(client, auth_headers):
    resp = client.get("/projects/DOES-NOT-EXIST", headers=auth_headers)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_project_detail_requires_auth(client, db_session):
    db_session.add(Project(project_id="WS/DETAIL/2", is_synthetic=True))
    db_session.commit()
    resp = client.get("/projects/WS%2FDETAIL%2F2")
    assert resp.status_code == 401


def test_project_detail_with_slash_in_id_is_handled(client, db_session, auth_headers):
    """Real MPLADS work_ids contain slashes (e.g. WS/MP235/2026-2027/1) --
    the route uses a :path converter specifically so a URL-encoded ID
    with embedded slashes still resolves to the right row."""
    db_session.add(Project(project_id="WS/MP235/2026-2027/999", is_synthetic=True))
    db_session.commit()

    resp = client.get("/projects/WS%2FMP235%2F2026-2027%2F999", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["project_id"] == "WS/MP235/2026-2027/999"