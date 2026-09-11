"""
Phase 4 tests: GET /analytics.

Uses the same fixtures as test_protected_routes.py (client, auth_headers,
db_session) from conftest.py. Project rows are inserted directly via
db_session, the same pattern used elsewhere in this suite, so each test
controls exactly what real data GET /analytics sees.
"""

from decimal import Decimal

from app.models import Project


def _make_project(db_session, **overrides):
    """Insert a minimal Project row and return it. Only project_id is
    required by the model -- every other column defaults to None/False
    unless overridden, so each test only has to specify what it cares
    about."""
    defaults = dict(
        project_id="WS/TEST/ANALYTICS/000001",
        state=None,
        work_type=None,
        status=None,
        sanctioned_amount=None,
        expenditure=None,
        estimated_cost=None,
        financial_progress=None,
        physical_progress=None,
        is_synthetic=True,
        risk_score=None,
        risk_level=None,
    )
    defaults.update(overrides)
    project = Project(**defaults)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


# --- Auth ---------------------------------------------------------------

def test_analytics_without_jwt_returns_401(client):
    resp = client.get("/analytics")
    assert resp.status_code == 401


def test_analytics_with_valid_jwt_returns_200(client, auth_headers):
    resp = client.get("/analytics", headers=auth_headers)
    assert resp.status_code == 200


def test_analytics_rejects_invalid_jwt(client):
    headers = {"Authorization": "Bearer not-a-real-token"}
    resp = client.get("/analytics", headers=headers)
    assert resp.status_code == 401


def test_openapi_marks_analytics_as_protected(client):
    schema = client.get("/openapi.json").json()
    op = schema["paths"]["/analytics"]["get"]
    assert bool(op.get("security")) is True


# --- Empty DB: fields must be present with correct empty/zero values ---

def test_analytics_empty_database(client, auth_headers):
    resp = client.get("/analytics", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_projects"] == 0
    assert body["risk_level_counts"] == {}
    assert body["by_state"] == []
    assert body["by_work_type"] == []
    assert body["status_distribution"] == []

    assert body["risk_score_summary"]["scored_project_count"] == 0
    assert body["risk_score_summary"]["average"] is None

    assert body["estimated_cost_summary"]["project_count_with_data"] == 0
    assert body["estimated_cost_summary"]["total"] is None


# --- Core totals / risk_level_counts match GET /dashboard/stats --------

def test_analytics_matches_dashboard_stats_on_shared_fields(client, db_session, auth_headers):
    _make_project(db_session, project_id="WS/A/1", risk_level="HIGH", state="Bihar",
                   sanctioned_amount=Decimal("100.00"), expenditure=Decimal("40.00"))
    _make_project(db_session, project_id="WS/A/2", risk_level="LOW", state="Bihar",
                   sanctioned_amount=Decimal("200.00"), expenditure=Decimal("150.00"))

    dashboard_body = client.get("/dashboard/stats", headers=auth_headers).json()
    analytics_body = client.get("/analytics", headers=auth_headers).json()

    for field in (
        "total_projects", "total_sanctioned_amount", "total_expenditure",
        "average_financial_progress", "average_physical_progress",
        "active_projects", "completed_projects", "delayed_projects",
        "risk_level_counts", "by_state", "by_work_type",
    ):
        assert analytics_body[field] == dashboard_body[field], f"mismatch on {field}"


# --- Risk score summary --------------------------------------------------

def test_analytics_risk_score_summary(client, db_session, auth_headers):
    _make_project(db_session, project_id="WS/R/1", risk_score=Decimal("10.00"))
    _make_project(db_session, project_id="WS/R/2", risk_score=Decimal("50.00"))
    _make_project(db_session, project_id="WS/R/3", risk_score=Decimal("90.00"))
    # A project with no risk_score at all must not be counted as scored,
    # and must not pull the average toward 0.
    _make_project(db_session, project_id="WS/R/4", risk_score=None)

    resp = client.get("/analytics", headers=auth_headers)
    body = resp.json()["risk_score_summary"]

    assert body["scored_project_count"] == 3
    assert float(body["average"]) == 50.0
    assert float(body["minimum"]) == 10.0
    assert float(body["maximum"]) == 90.0


# --- Estimated cost summary: NULL-heavy field handled explicitly -------

def test_analytics_estimated_cost_summary_with_data(client, db_session, auth_headers):
    _make_project(db_session, project_id="WS/C/1", estimated_cost=Decimal("1000.00"))
    _make_project(db_session, project_id="WS/C/2", estimated_cost=Decimal("3000.00"))
    _make_project(db_session, project_id="WS/C/3", estimated_cost=None)

    resp = client.get("/analytics", headers=auth_headers)
    body = resp.json()["estimated_cost_summary"]

    assert body["project_count_with_data"] == 2
    assert float(body["total"]) == 4000.0
    assert float(body["average"]) == 2000.0
    assert float(body["minimum"]) == 1000.0
    assert float(body["maximum"]) == 3000.0


def test_analytics_estimated_cost_summary_all_null(client, db_session, auth_headers):
    """Represents the real Phase 2 dataset: no project has a source
    value for estimated_cost. Must report null/0, never a fabricated
    number."""
    _make_project(db_session, project_id="WS/C/4", estimated_cost=None)
    _make_project(db_session, project_id="WS/C/5", estimated_cost=None)

    resp = client.get("/analytics", headers=auth_headers)
    body = resp.json()["estimated_cost_summary"]

    assert body["project_count_with_data"] == 0
    assert body["total"] is None
    assert body["average"] is None
    assert body["minimum"] is None
    assert body["maximum"] is None


# --- Progress summaries --------------------------------------------------

def test_analytics_progress_summaries(client, db_session, auth_headers):
    _make_project(db_session, project_id="WS/P/1", financial_progress=Decimal("20.00"), physical_progress=None)
    _make_project(db_session, project_id="WS/P/2", financial_progress=Decimal("80.00"), physical_progress=Decimal("60.00"))

    resp = client.get("/analytics", headers=auth_headers)
    body = resp.json()

    fin = body["financial_progress_summary"]
    assert fin["project_count_with_data"] == 2
    assert float(fin["average"]) == 50.0

    phys = body["physical_progress_summary"]
    # Only one of the two projects has a physical_progress value -- the
    # NULL one must not count as 0.
    assert phys["project_count_with_data"] == 1
    assert float(phys["average"]) == 60.0


# --- Status distribution --------------------------------------------------

def test_analytics_status_distribution_folds_null_into_not_specified(client, db_session, auth_headers):
    _make_project(db_session, project_id="WS/S/1", status="Completed")
    _make_project(db_session, project_id="WS/S/2", status="Ongoing")
    _make_project(db_session, project_id="WS/S/3", status=None)
    _make_project(db_session, project_id="WS/S/4", status=None)

    resp = client.get("/analytics", headers=auth_headers)
    rows = {r["status"]: r["count"] for r in resp.json()["status_distribution"]}

    assert rows["Completed"] == 1
    assert rows["Ongoing"] == 1
    assert rows["Not specified"] == 2
    assert sum(rows.values()) == 4  # every project accounted for


# --- Existing endpoints remain unaffected ---------------------------------

def test_dashboard_stats_still_works_after_analytics_refactor(client, db_session, auth_headers):
    _make_project(db_session, project_id="WS/D/1", risk_level="MEDIUM")

    resp = client.get("/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total_projects"] == 1
    assert resp.json()["risk_level_counts"] == {"MEDIUM": 1}


def test_projects_and_alerts_still_work_after_analytics_addition(client, db_session, auth_headers):
    _make_project(db_session, project_id="WS/E/1", risk_level="HIGH", risk_score=Decimal("70.00"))

    projects_resp = client.get("/projects", headers=auth_headers)
    assert projects_resp.status_code == 200
    assert len(projects_resp.json()) == 1

    alerts_resp = client.get("/alerts", headers=auth_headers)
    assert alerts_resp.status_code == 200