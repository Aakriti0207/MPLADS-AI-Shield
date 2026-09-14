"""
Phase 8 tests: GET /reports/meta, GET /reports/generate, GET /reports/project/{id}.

Uses the same fixtures as the rest of the suite (client, auth_headers,
admin_auth_headers, db_session -- see conftest.py). Project rows are
inserted directly via db_session, the same pattern used by
test_analytics.py, so each test controls exactly what real data the
report sees.
"""

from decimal import Decimal

from app.models import Project


def _make_project(db_session, **overrides):
    defaults = dict(
        project_id="WS/TEST/REPORTS/000001",
        state=None,
        district=None,
        constituency=None,
        work_type=None,
        status=None,
        sanctioned_amount=None,
        expenditure=None,
        financial_progress=None,
        is_synthetic=True,
        risk_score=None,
        risk_level=None,
        risk_reason_1=None,
        duplicate_risk_score=None,
        anomaly_risk_score=None,
    )
    defaults.update(overrides)
    project = Project(**defaults)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


# --- Auth / basic access --------------------------------------------------

def test_reports_meta_without_jwt_returns_401(client):
    resp = client.get("/reports/meta")
    assert resp.status_code == 401


def test_reports_generate_without_jwt_returns_401(client):
    resp = client.get("/reports/generate", params={"report_type": "project_monitoring"})
    assert resp.status_code == 401


# --- Role scoping (mirrors GET /dashboard/role-overview) ------------------

def test_reports_meta_unavailable_for_non_ministry_role(client, auth_headers):
    """`registered_user`/`auth_headers` is a "District Authority" account
    -- no state/district/constituency scope exists on User, so scoped
    reporting must be reported as unavailable, never silently given the
    national report under a false label."""
    resp = client.get("/reports/meta", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope_available"] is False
    assert body["report_types"] == []
    assert "not available" in body["unavailable_reason"].lower()


def test_reports_meta_available_for_ministry_admin(client, admin_auth_headers):
    resp = client.get("/reports/meta", headers=admin_auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope_available"] is True
    assert body["scope_label"] == "National"
    ids = {t["id"] for t in body["report_types"]}
    assert ids == {"project_monitoring", "risk_anomaly"}
    assert set(body["export_formats"]) == {"json", "csv", "pdf"}


def test_reports_generate_forbidden_for_non_ministry_role(client, auth_headers):
    """Backend-side enforcement, independent of the frontend ever
    checking /reports/meta first."""
    resp = client.get(
        "/reports/generate",
        params={"report_type": "project_monitoring"},
        headers=auth_headers,
    )
    assert resp.status_code == 403


# --- Unsupported inputs -----------------------------------------------

def test_reports_generate_rejects_unsupported_report_type(client, admin_auth_headers):
    resp = client.get(
        "/reports/generate",
        params={"report_type": "not_a_real_type"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 400


def test_reports_generate_rejects_unsupported_format(client, admin_auth_headers):
    resp = client.get(
        "/reports/generate",
        params={"report_type": "project_monitoring", "format": "xlsx"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 400


# --- Real data, not fake numbers ---------------------------------------

def test_reports_generate_json_totals_match_real_project_rows(client, admin_auth_headers, db_session):
    _make_project(
        db_session,
        project_id="WS/TEST/REPORTS/000001",
        state="Delhi",
        sanctioned_amount=Decimal("1000000.00"),
        expenditure=Decimal("400000.00"),
        risk_level="HIGH",
        risk_score=Decimal("70.00"),
        risk_reason_1="Expenditure recorded without a matching sanction record.",
    )
    _make_project(
        db_session,
        project_id="WS/TEST/REPORTS/000002",
        state="Delhi",
        sanctioned_amount=Decimal("500000.00"),
        expenditure=Decimal("500000.00"),
        risk_level="LOW",
        risk_score=Decimal("10.00"),
    )

    resp = client.get(
        "/reports/generate",
        params={"report_type": "project_monitoring", "format": "json"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_projects"] == 2
    assert Decimal(body["total_sanctioned_amount"]) == Decimal("1500000.00")
    assert Decimal(body["total_expenditure"]) == Decimal("900000.00")
    assert body["risk_level_counts"] == {"HIGH": 1, "LOW": 1}
    assert body["projects_requiring_review"] == 1
    assert len(body["priority_projects"]) == 1
    assert body["priority_projects"][0]["project_id"] == "WS/TEST/REPORTS/000001"
    assert body["priority_projects"][0]["risk_reasons"] == [
        "Expenditure recorded without a matching sanction record."
    ]
    assert "does not establish fraud" in body["disclaimer"].lower()


def test_reports_generate_applies_state_filter(client, admin_auth_headers, db_session):
    _make_project(db_session, project_id="WS/TEST/REPORTS/000001", state="Delhi", sanctioned_amount=Decimal("100.00"))
    _make_project(db_session, project_id="WS/TEST/REPORTS/000002", state="Bihar", sanctioned_amount=Decimal("200.00"))

    resp = client.get(
        "/reports/generate",
        params={"report_type": "project_monitoring", "format": "json", "state": "Delhi"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_projects"] == 1
    assert body["scope"] == "State: Delhi"


def test_reports_generate_missing_data_reported_as_not_available_not_zero(client, admin_auth_headers, db_session):
    """No risk-scored projects in scope -> risk_level_counts is empty and
    a data-quality note is added, never a fabricated zero count."""
    _make_project(db_session, project_id="WS/TEST/REPORTS/000001", state="Kerala", risk_level=None)

    resp = client.get(
        "/reports/generate",
        params={"report_type": "project_monitoring", "format": "json"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_level_counts"] == {}
    assert any("risk scoring is not available" in note.lower() for note in body["data_quality_notes"])


# --- Real file downloads ------------------------------------------------

def test_reports_generate_csv_returns_real_file(client, admin_auth_headers, db_session):
    _make_project(
        db_session,
        project_id="WS/TEST/REPORTS/000001",
        state="Delhi",
        work_type="Road construction",
        sanctioned_amount=Decimal("100000.00"),
        expenditure=Decimal("50000.00"),
        risk_level="HIGH",
        risk_score=Decimal("60.00"),
    )

    resp = client.get(
        "/reports/generate",
        params={"report_type": "project_monitoring", "format": "csv"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    text = resp.text
    assert "Work ID" in text.splitlines()[0]
    assert "WS/TEST/REPORTS/000001" in text
    assert "Road construction" in text


def test_reports_generate_pdf_returns_real_pdf_bytes(client, admin_auth_headers, db_session):
    _make_project(db_session, project_id="WS/TEST/REPORTS/000001", state="Delhi", sanctioned_amount=Decimal("100.00"))

    resp = client.get(
        "/reports/generate",
        params={"report_type": "risk_anomaly", "format": "pdf"},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.content[:4] == b"%PDF"


# --- Project-level report (any authenticated user, like GET /projects/{id}) --

def test_reports_project_report_requires_auth(client, db_session):
    _make_project(db_session, project_id="WS/TEST/REPORTS/000001")
    resp = client.get("/reports/project/WS%2FTEST%2FREPORTS%2F000001")
    assert resp.status_code == 401


def test_reports_project_report_available_to_ordinary_authenticated_role(client, auth_headers, db_session):
    _make_project(db_session, project_id="WS/TEST/REPORTS/000001", state="Delhi")
    resp = client.get("/reports/project/WS%2FTEST%2FREPORTS%2F000001", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


def test_reports_project_report_404_for_unknown_project(client, auth_headers):
    resp = client.get("/reports/project/WS%2FDOES%2FNOT%2FEXIST", headers=auth_headers)
    assert resp.status_code == 404


def test_reports_project_report_json_format(client, auth_headers, db_session):
    _make_project(
        db_session,
        project_id="WS/TEST/REPORTS/000001",
        state="Delhi",
        risk_level="MEDIUM",
        risk_score=Decimal("40.00"),
    )
    resp = client.get(
        "/reports/project/WS%2FTEST%2FREPORTS%2F000001",
        params={"format": "json"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] == "WS/TEST/REPORTS/000001"
    assert body["risk_level"] == "MEDIUM"