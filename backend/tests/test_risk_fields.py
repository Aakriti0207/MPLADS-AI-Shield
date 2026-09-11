"""
Phase 3 tests: risk score / risk level / risk reasons exposure.

These tests exist to lock in behavior of the ALREADY-IMPLEMENTED Phase 2
risk pipeline (models.Project's risk_* columns -> schemas.ProjectOut ->
GET /projects/{id}, GET /dashboard/stats, GET /alerts). Nothing about the
risk calculation itself is touched here -- these tests insert rows
directly into the test DB with pre-computed risk values (standing in for
what import_phase2.py would have loaded from project_risk_scores.csv)
and assert the API surfaces them correctly, including the NULL/sparse
cases that are the real, common case for risk_reason_1/2/3 in production
(see app/models.py's Project docstring: reasons are populated for only a
handful of the 56,323 real rows).

Uses the same `client` / `auth_headers` / `db_session` fixtures as
test_protected_routes.py and test_auth.py (see conftest.py).
"""

from decimal import Decimal

from app.models import Project


def _make_project(db_session, **overrides):
    """Insert a minimal-but-realistic Project row and return it.

    Only project_id is required by the model; every other column here
    is set explicitly so each test can override just what it cares
    about via **overrides, without every test having to restate the
    full set of risk fields.
    """
    defaults = dict(
        project_id="WS/TEST/2024-2025/000001",
        state="Test State",
        work_type="Test Work",
        sanctioned_amount=Decimal("1000000.00"),
        expenditure=Decimal("500000.00"),
        is_synthetic=True,
        risk_score=Decimal("67.30"),
        risk_level="HIGH",
        financial_risk_score=Decimal("80.00"),
        payment_risk_score=Decimal("45.00"),
        execution_risk_score=Decimal("30.00"),
        peer_anomaly_score=Decimal("20.00"),
        isolation_forest_score=Decimal("15.00"),
        anomaly_risk_score=Decimal("10.00"),
        duplicate_risk_score=Decimal("5.00"),
        raw_max_similarity=Decimal("0.1716"),
        most_similar_work_id="WS/TEST/2024-2025/000002",
        risk_reason_1="Expenditure is recorded for this project but no matching sanction record exists in this snapshot.",
        risk_reason_2="A single vendor accounts for an unusually large share of this project's recorded transactions.",
        risk_reason_3=None,
        risk_metadata={"work_category": "Test category", "n_distinct_vendors": 3},
    )
    defaults.update(overrides)
    project = Project(**defaults)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


# --- GET /projects/{project_id}: risk fields are exposed correctly -----

def test_project_detail_exposes_risk_score_and_level(client, db_session, auth_headers):
    _make_project(db_session)

    resp = client.get(
        "/projects/WS%2FTEST%2F2024-2025%2F000001", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()

    assert float(body["risk_score"]) == 67.3
    assert body["risk_level"] == "HIGH"


def test_project_detail_exposes_risk_reasons_and_metadata(client, db_session, auth_headers):
    _make_project(db_session)

    resp = client.get(
        "/projects/WS%2FTEST%2F2024-2025%2F000001", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["risk_reason_1"].startswith("Expenditure is recorded")
    assert body["risk_reason_2"].startswith("A single vendor")
    # risk_reason_3 was never set for this project -- must come back as
    # null, never fabricated/defaulted to an empty string or a made-up reason.
    assert body["risk_reason_3"] is None

    assert body["risk_metadata"]["work_category"] == "Test category"
    assert body["risk_metadata"]["n_distinct_vendors"] == 3

    # Risk sub-scores and similarity fields are part of the same
    # "why is this risky" contract -- confirm they round-trip too.
    assert float(body["financial_risk_score"]) == 80.0
    assert float(body["raw_max_similarity"]) == 0.1716
    assert body["most_similar_work_id"] == "WS/TEST/2024-2025/000002"


def test_project_detail_null_risk_fields_do_not_crash_serialization(client, db_session, auth_headers):
    """A project that hasn't gone through the Phase 2 risk pipeline at
    all (all risk_* columns NULL) must still serialize cleanly -- this
    is the realistic case for is_synthetic seed rows and any future
    not-yet-scored project."""
    _make_project(
        db_session,
        project_id="WS/TEST/2024-2025/000003",
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

    resp = client.get(
        "/projects/WS%2FTEST%2F2024-2025%2F000003", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["risk_score"] is None
    assert body["risk_level"] is None
    assert body["risk_reason_1"] is None
    assert body["risk_reason_2"] is None
    assert body["risk_reason_3"] is None
    assert body["risk_metadata"] is None


def test_project_detail_nonexistent_project_returns_404(client, db_session, auth_headers):
    _make_project(db_session)  # unrelated row present; must not affect this

    resp = client.get("/projects/DOES-NOT-EXIST", headers=auth_headers)
    assert resp.status_code == 404


# --- GET /dashboard/stats: risk_level_counts reflects real DB rows -----

def test_dashboard_risk_level_counts_match_seeded_projects(client, db_session, auth_headers):
    _make_project(db_session, project_id="WS/TEST/2024-2025/H1", risk_level="HIGH")
    _make_project(db_session, project_id="WS/TEST/2024-2025/H2", risk_level="HIGH")
    _make_project(db_session, project_id="WS/TEST/2024-2025/M1", risk_level="MEDIUM")
    _make_project(db_session, project_id="WS/TEST/2024-2025/L1", risk_level="LOW")
    # A not-yet-scored project (NULL risk_level) must be excluded from
    # every bucket, not silently folded into one.
    _make_project(db_session, project_id="WS/TEST/2024-2025/N1", risk_level=None)

    resp = client.get("/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200
    counts = resp.json()["risk_level_counts"]

    assert counts["HIGH"] == 2
    assert counts["MEDIUM"] == 1
    assert counts["LOW"] == 1
    assert "null" not in counts and None not in counts
    assert sum(counts.values()) == 4  # the NULL-risk_level row is excluded


# --- GET /alerts: alerts stay consistent with the same project risk data ---

def test_alerts_reflect_same_risk_level_as_project_detail(client, db_session, auth_headers):
    _make_project(
        db_session,
        project_id="WS/TEST/2024-2025/HIGHRISK",
        risk_level="HIGH",
        risk_score=Decimal("72.00"),
        risk_reason_1="Test reason for alert consistency check.",
        risk_reason_2=None,
        risk_reason_3=None,
    )

    project_resp = client.get(
        "/projects/WS%2FTEST%2F2024-2025%2FHIGHRISK", headers=auth_headers
    )
    assert project_resp.status_code == 200
    project_body = project_resp.json()

    alerts_resp = client.get("/alerts", headers=auth_headers)
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()

    matching = [a for a in alerts if a["project_id"] == "WS/TEST/2024-2025/HIGHRISK"]
    assert len(matching) >= 1

    high_risk_alert = next(a for a in matching if a["alert_type"] == "high_risk_project")
    # Severity must be derived from the SAME risk_level the project
    # endpoint returns, not a separately maintained value.
    assert high_risk_alert["severity"] == project_body["risk_level"].lower()
    # The alert message must be built from the project's real risk
    # reason, not a fabricated one.
    assert "Test reason for alert consistency check." in high_risk_alert["message"]


def test_alerts_do_not_include_low_risk_projects_without_other_signals(client, db_session, auth_headers):
    _make_project(
        db_session,
        project_id="WS/TEST/2024-2025/LOWRISK",
        risk_level="LOW",
        risk_score=Decimal("10.00"),
        financial_risk_score=Decimal("5.00"),
        payment_risk_score=Decimal("5.00"),
        execution_risk_score=Decimal("5.00"),
        peer_anomaly_score=Decimal("5.00"),
        isolation_forest_score=Decimal("5.00"),
        anomaly_risk_score=Decimal("5.00"),
        duplicate_risk_score=Decimal("5.00"),
        raw_max_similarity=None,
        most_similar_work_id=None,
        risk_reason_1=None,
        risk_reason_2=None,
        risk_reason_3=None,
    )

    resp = client.get("/alerts", headers=auth_headers)
    assert resp.status_code == 200
    alerts = resp.json()

    assert all(a["project_id"] != "WS/TEST/2024-2025/LOWRISK" for a in alerts)


# --- Existing behavior must remain intact -------------------------------

def test_projects_detail_without_jwt_still_returns_401(client, db_session):
    _make_project(db_session)
    resp = client.get("/projects/WS%2FTEST%2F2024-2025%2F000001")
    assert resp.status_code == 401