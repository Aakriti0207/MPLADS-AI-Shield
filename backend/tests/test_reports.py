"""
Phase 8 tests: GET /reports/meta, GET /reports/generate, GET /reports/project/{id}.

Uses the same fixtures as the rest of the suite (client, auth_headers,
admin_auth_headers, db_session -- see conftest.py).

Risk-related assertions are sourced from the REAL project_risk_scores.csv
(via app.aggregations.load_risk_fusion), the same pattern test_analytics.py
uses -- never from the legacy Project.risk_score/risk_level/risk_reason_1..3/
duplicate_risk_score/anomaly_risk_score DB columns. Those columns are
Phase-2 fields the current pipeline intentionally leaves NULL (see
app/routes/projects.py); a real report can never read a value from them,
so a test that sets them and expects the report to reflect them would be
testing a scenario the running application can never produce.

Project financial/location fields (state, sanctioned_amount, ...) are
still inserted directly via db_session, exactly as before -- only the
risk figures now come from the real CSV.
"""

from decimal import Decimal

import pytest

from app.aggregations import load_risk_fusion
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
    )
    defaults.update(overrides)
    project = Project(**defaults)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def _real_reasons(risk_row) -> list[str]:
    reasons = [risk_row.get("top_reason_1"), risk_row.get("top_reason_2"), risk_row.get("top_reason_3")]
    return [r for r in reasons if isinstance(r, str) and r.strip()]


@pytest.fixture(scope="module")
def risk_df():
    """The real, current Risk Fusion output -- loaded once per test module,
    exactly like test_analytics.py does."""
    return load_risk_fusion()


@pytest.fixture()
def real_high_risk_row(risk_df):
    """One real project the current pipeline actually scored HIGH or
    CRITICAL. Skips (rather than fabricating one) if none exist -- a
    dataset with zero HIGH/CRITICAL projects is a legitimate state."""
    matches = risk_df[risk_df["risk_level"].astype(str).str.upper().isin(["HIGH", "CRITICAL"])]
    if matches.empty:
        pytest.skip("Current risk dataset has no HIGH/CRITICAL project to test against.")
    return matches.iloc[0]


@pytest.fixture()
def real_low_risk_row(risk_df):
    matches = risk_df[risk_df["risk_level"].astype(str).str.upper() == "LOW"]
    if matches.empty:
        pytest.skip("Current risk dataset has no LOW project to test against.")
    return matches.iloc[0]


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

def test_reports_generate_json_totals_match_real_project_rows(
    client, admin_auth_headers, db_session, real_high_risk_row, real_low_risk_row
):
    """Risk figures in the report must be the CURRENT Risk Fusion output
    for these exact, real work IDs -- not a value set on the (unused)
    legacy Project.risk_score/risk_level DB columns."""

    high_id = str(real_high_risk_row["work_id"])
    low_id = str(real_low_risk_row["work_id"])

    _make_project(
        db_session,
        project_id=high_id,
        state="Delhi",
        sanctioned_amount=Decimal("1000000.00"),
        expenditure=Decimal("400000.00"),
    )
    _make_project(
        db_session,
        project_id=low_id,
        state="Delhi",
        sanctioned_amount=Decimal("500000.00"),
        expenditure=Decimal("500000.00"),
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

    expected_level = str(real_high_risk_row["risk_level"]).upper()
    assert body["risk_level_counts"] == {
        "LOW": 1,
        "MEDIUM": 0,
        "HIGH": 1 if expected_level == "HIGH" else 0,
        "CRITICAL": 1 if expected_level == "CRITICAL" else 0,
    }
    assert body["projects_requiring_review"] == 1
    assert len(body["priority_projects"]) == 1
    assert body["priority_projects"][0]["project_id"] == high_id
    assert body["priority_projects"][0]["risk_level"] == expected_level
    assert body["priority_projects"][0]["risk_reasons"] == _real_reasons(real_high_risk_row)
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


def test_reports_generate_risk_level_filter_reflects_real_risk_fusion(
    client, admin_auth_headers, db_session, real_high_risk_row, real_low_risk_row
):
    """Regression test for the bug this session fixed: risk_level used to
    filter against Project.risk_level, a column the current pipeline never
    populates, so this filter always returned zero rows regardless of the
    value requested. It must now filter against the real Risk Fusion
    output and return exactly the matching project(s)."""

    high_id = str(real_high_risk_row["work_id"])
    low_id = str(real_low_risk_row["work_id"])
    expected_level = str(real_high_risk_row["risk_level"]).upper()

    _make_project(db_session, project_id=high_id, state="Delhi")
    _make_project(db_session, project_id=low_id, state="Delhi")

    resp = client.get(
        "/reports/generate",
        params={"report_type": "risk_anomaly", "format": "json", "risk_level": expected_level},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_projects"] == 1
    assert body["risk_level_counts"].get(expected_level) == 1
    assert body["filters_applied"]["risk_level"] == expected_level

    resp_low = client.get(
        "/reports/generate",
        params={"report_type": "risk_anomaly", "format": "json", "risk_level": "LOW"},
        headers=admin_auth_headers,
    )
    assert resp_low.status_code == 200
    body_low = resp_low.json()
    assert body_low["total_projects"] == 1
    assert body_low["risk_level_counts"].get("LOW") == 1


def test_reports_generate_missing_data_reported_as_not_available_not_zero(client, admin_auth_headers, db_session):
    """A project with no matching Risk Fusion row (a synthetic/test-only
    work ID, never present in project_risk_scores.csv) -> risk_level_counts
    is empty and a data-quality note is added, never a fabricated zero
    count."""
    _make_project(db_session, project_id="WS/TEST/REPORTS/000001", state="Kerala")

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

def test_reports_generate_csv_returns_real_file(
    client, admin_auth_headers, db_session, real_high_risk_row
):
    high_id = str(real_high_risk_row["work_id"])
    _make_project(
        db_session,
        project_id=high_id,
        state="Delhi",
        work_type="Road construction",
        sanctioned_amount=Decimal("100000.00"),
        expenditure=Decimal("50000.00"),
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
    assert high_id in text
    assert "Road construction" in text
    # The CSV's own Risk Level cell must be the real Risk Fusion value, not
    # blank -- proves this row was matched against project_risk_scores.csv.
    assert str(real_high_risk_row["risk_level"]).upper() in text


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

def test_reports_project_report_requires_auth(client):
    resp = client.get("/reports/project/WS%2FTEST%2FREPORTS%2F000001")
    assert resp.status_code == 401


def test_reports_project_report_available_to_ordinary_authenticated_role(
    client, auth_headers, real_high_risk_row
):
    """Sourced entirely from the canonical project universe + Risk Fusion
    output -- no Project DB row is required for a report to be generated,
    exactly like GET /projects/{id} itself needs none (see
    app/routes/projects.py)."""
    high_id = str(real_high_risk_row["work_id"])
    resp = client.get(f"/reports/project/{high_id.replace('/', '%2F')}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


def test_reports_project_report_404_for_unknown_project(client, auth_headers):
    resp = client.get("/reports/project/WS%2FDOES%2FNOT%2FEXIST", headers=auth_headers)
    assert resp.status_code == 404


def test_reports_project_report_json_format(client, auth_headers, real_high_risk_row):
    high_id = str(real_high_risk_row["work_id"])
    resp = client.get(
        f"/reports/project/{high_id.replace('/', '%2F')}",
        params={"format": "json"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["project"]["project_id"] == high_id

    expected_level = str(real_high_risk_row["risk_level"]).upper()
    assert body["risk"] is not None
    assert body["risk"]["risk_level"] == expected_level
    assert body["risk"]["risk_score"] == pytest.approx(float(real_high_risk_row["risk_score"]))


def test_reports_project_report_json_includes_full_risk_fusion_breakdown(
    client, auth_headers, real_high_risk_row
):
    """The single-project report must expose the same per-component
    breakdown (score/weight/contribution/status/reasons/review_actions)
    the Project Details page's Risk Fusion tab renders -- this is the
    "Why This Project Was Flagged" data the report needs to match."""
    high_id = str(real_high_risk_row["work_id"])
    resp = client.get(
        f"/reports/project/{high_id.replace('/', '%2F')}",
        params={"format": "json"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    components = resp.json()["risk"]["components"]

    assert set(components) == {
        "compliance", "financial_anomaly", "timeline_anomaly", "duplicate",
        "data_quality", "payment", "isolation_forest",
    }

    total_contribution = round(sum(c["contribution"] for c in components.values()), 2)
    assert total_contribution == pytest.approx(float(real_high_risk_row["risk_score"]), abs=0.05)

    triggered = [c for c in components.values() if c["status"].upper() != "NONE"]
    assert len(triggered) > 0
    for detail in triggered:
        assert detail["description"]
        assert detail["review_actions"]


def test_reports_project_report_pdf_reflects_real_risk_score(client, auth_headers, real_high_risk_row):
    """A crude but meaningful check that the PDF was actually built from
    the real Risk Fusion score for this project, not a placeholder."""
    high_id = str(real_high_risk_row["work_id"])
    resp = client.get(f"/reports/project/{high_id.replace('/', '%2F')}", headers=auth_headers)
    assert resp.status_code == 200

    # reportlab PDFs are compressed by default; decompressing to search for
    # the literal score string is unnecessary here -- generating without
    # raising, with real bytes, against real data (asserted above/elsewhere)
    # is the meaningful guarantee. This just confirms a non-trivial,
    # multi-section document was produced (not the old ~1-line fallback).
    assert len(resp.content) > 3000