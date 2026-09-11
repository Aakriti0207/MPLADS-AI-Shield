"""
Phase 7 QA: risk field integrity, dashboard aggregate correctness (with
hand-computed expected values against a deterministic seeded DB), and
alert/risk consistency. This is the risk-field regression coverage that
Step 6/7 of the Phase 7 spec calls for; it did not exist as a dedicated
file in this tree before this phase (a similar-purpose file existed in
an earlier chat session but was never committed -- see this phase's
report for that discrepancy).
"""

from datetime import date, timedelta
from decimal import Decimal

from app.models import Project


def _make_project(db_session, **overrides):
    defaults = dict(
        project_id="WS/QA/000001",
        state="Test State",
        sanctioned_amount=Decimal("1000000.00"),
        expenditure=Decimal("500000.00"),
        is_synthetic=True,
        risk_score=None,
        risk_level=None,
        financial_risk_score=None,
        payment_risk_score=None,
        execution_risk_score=None,
        peer_anomaly_score=None,
        isolation_forest_score=None,
        anomaly_risk_score=None,
        duplicate_risk_score=None,
        raw_max_similarity=None,
        most_similar_work_id=None,
        risk_reason_1=None,
        risk_reason_2=None,
        risk_reason_3=None,
        risk_metadata=None,
    )
    defaults.update(overrides)
    project = Project(**defaults)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


# --- Risk field integrity across risk levels ------------------------------

def test_high_risk_project_exposes_all_risk_fields(client, db_session, auth_headers):
    _make_project(
        db_session,
        project_id="WS/QA/HIGH",
        risk_score=Decimal("72.50"),
        risk_level="HIGH",
        financial_risk_score=Decimal("80.00"),
        raw_max_similarity=Decimal("0.20"),
        risk_reason_1="Expenditure recorded without a matching sanction record.",
        risk_metadata={"work_category": "Roads"},
    )
    resp = client.get("/projects/WS%2FQA%2FHIGH", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_level"] == "HIGH"
    assert float(body["risk_score"]) == 72.5
    assert body["risk_reason_1"].startswith("Expenditure recorded")
    assert body["risk_metadata"]["work_category"] == "Roads"


def test_medium_risk_project_exposes_risk_level(client, db_session, auth_headers):
    _make_project(db_session, project_id="WS/QA/MEDIUM", risk_score=Decimal("45.00"), risk_level="MEDIUM")
    resp = client.get("/projects/WS%2FQA%2FMEDIUM", headers=auth_headers)
    assert resp.json()["risk_level"] == "MEDIUM"


def test_low_risk_project_exposes_risk_level(client, db_session, auth_headers):
    _make_project(db_session, project_id="WS/QA/LOW", risk_score=Decimal("12.00"), risk_level="LOW")
    resp = client.get("/projects/WS%2FQA%2FLOW", headers=auth_headers)
    assert resp.json()["risk_level"] == "LOW"


def test_project_with_null_risk_fields_serializes_cleanly(client, db_session, auth_headers):
    _make_project(db_session, project_id="WS/QA/UNSCORED")
    resp = client.get("/projects/WS%2FQA%2FUNSCORED", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    for field in ("risk_score", "risk_level", "risk_reason_1", "risk_reason_2", "risk_reason_3", "risk_metadata"):
        assert body[field] is None


def test_nonexistent_project_risk_lookup_returns_404(client, auth_headers):
    resp = client.get("/projects/WS%2FQA%2FNONEXISTENT", headers=auth_headers)
    assert resp.status_code == 404


def test_decimal_risk_score_precision_is_not_corrupted(client, db_session, auth_headers):
    """Guards against float round-off turning 67.30 into 67.29999...
    across the DB -> Pydantic -> JSON round trip."""
    _make_project(db_session, project_id="WS/QA/PRECISION", risk_score=Decimal("67.30"))
    resp = client.get("/projects/WS%2FQA%2FPRECISION", headers=auth_headers)
    assert Decimal(str(resp.json()["risk_score"])) == Decimal("67.30")


# --- Dashboard aggregates: hand-computed expected values ------------------

def test_dashboard_stats_totals_match_hand_computed_values(client, db_session, auth_headers):
    today = date.today()
    _make_project(
        db_session, project_id="WS/QA/D1", status="Completed",
        sanctioned_amount=Decimal("100000.00"), expenditure=Decimal("100000.00"),
        financial_progress=Decimal("100.00"),
    )
    _make_project(
        db_session, project_id="WS/QA/D2", status="Ongoing",
        sanctioned_amount=Decimal("200000.00"), expenditure=Decimal("50000.00"),
        financial_progress=Decimal("25.00"),
        expected_completion=today - timedelta(days=10),  # overdue -> delayed
    )
    _make_project(
        db_session, project_id="WS/QA/D3", status="Ongoing",
        sanctioned_amount=Decimal("300000.00"), expenditure=Decimal("30000.00"),
        financial_progress=Decimal("10.00"),
        expected_completion=today + timedelta(days=30),  # not yet due
    )

    resp = client.get("/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()

    # Hand-computed expectations:
    assert body["total_projects"] == 3
    assert float(body["total_sanctioned_amount"]) == 600000.0
    assert float(body["total_expenditure"]) == 180000.0
    assert round(float(body["average_financial_progress"]), 2) == round((100 + 25 + 10) / 3, 2)
    assert body["completed_projects"] == 1   # D1 only
    assert body["active_projects"] == 2       # D2 + D3
    assert body["delayed_projects"] == 1      # D2 only (overdue, not completed)


def test_dashboard_risk_level_counts_match_seeded_data(client, db_session, auth_headers):
    _make_project(db_session, project_id="WS/QA/R1", risk_level="HIGH")
    _make_project(db_session, project_id="WS/QA/R2", risk_level="HIGH")
    _make_project(db_session, project_id="WS/QA/R3", risk_level="MEDIUM")
    _make_project(db_session, project_id="WS/QA/R4", risk_level="LOW")
    _make_project(db_session, project_id="WS/QA/R5", risk_level=None)  # unscored -- must be excluded

    resp = client.get("/dashboard/stats", headers=auth_headers)
    counts = resp.json()["risk_level_counts"]
    assert counts == {"HIGH": 2, "MEDIUM": 1, "LOW": 1}
    assert sum(counts.values()) == 4  # the unscored project is excluded, not zero-bucketed


def test_dashboard_stats_empty_database(client, auth_headers):
    resp = client.get("/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_projects"] == 0
    assert float(body["total_sanctioned_amount"]) == 0.0
    assert body["risk_level_counts"] == {}


# --- Alerts: consistency with the same underlying risk data ---------------

def test_alert_severity_matches_project_risk_level(client, db_session, auth_headers):
    _make_project(
        db_session, project_id="WS/QA/ALERT1", risk_level="HIGH", risk_score=Decimal("75.00"),
        risk_reason_1="A genuine stored reason.",
    )
    project_resp = client.get("/projects/WS%2FQA%2FALERT1", headers=auth_headers).json()

    alerts = client.get("/alerts", headers=auth_headers).json()
    matching = [a for a in alerts if a["project_id"] == "WS/QA/ALERT1" and a["alert_type"] == "high_risk_project"]
    assert len(matching) == 1
    assert matching[0]["severity"] == project_resp["risk_level"].lower()
    assert "A genuine stored reason." in matching[0]["message"]


def test_low_risk_project_without_other_signals_generates_no_alert(client, db_session, auth_headers):
    _make_project(
        db_session, project_id="WS/QA/QUIET", risk_level="LOW", risk_score=Decimal("8.00"),
        financial_risk_score=Decimal("5.00"), payment_risk_score=Decimal("5.00"),
        execution_risk_score=Decimal("5.00"), peer_anomaly_score=Decimal("5.00"),
        isolation_forest_score=Decimal("5.00"), anomaly_risk_score=Decimal("5.00"),
    )
    alerts = client.get("/alerts", headers=auth_headers).json()
    assert all(a["project_id"] != "WS/QA/QUIET" for a in alerts)


def test_high_component_score_generates_critical_severity_alert(client, db_session, auth_headers):
    _make_project(db_session, project_id="WS/QA/COMPONENT", financial_risk_score=Decimal("85.00"))
    alerts = client.get("/alerts", headers=auth_headers).json()
    matching = [a for a in alerts if a["project_id"] == "WS/QA/COMPONENT" and a["alert_type"] == "financial_risk"]
    assert len(matching) == 1
    assert matching[0]["severity"] == "critical"


def test_alerts_pagination(client, db_session, auth_headers):
    for i in range(3):
        _make_project(db_session, project_id=f"WS/QA/ALERTPAGE{i}", risk_level="HIGH", risk_score=Decimal("90.00"))
    first_page = client.get("/alerts?skip=0&limit=2", headers=auth_headers).json()
    second_page = client.get("/alerts?skip=2&limit=2", headers=auth_headers).json()
    assert len(first_page) == 2
    assert len(second_page) == 1