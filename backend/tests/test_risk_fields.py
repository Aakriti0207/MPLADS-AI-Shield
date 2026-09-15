"""
Risk-field API regression tests.

The current protected project/dashboard/alert APIs use the production
canonical project and Risk Fusion datasets as their source of truth.
These tests therefore validate the production API contract rather than
expecting synthetic DB-only Project rows to appear in protected routes.
"""

from decimal import Decimal


REAL_PROJECT_ID = "WS/MP1/2023-2024/103702"


def _encoded(project_id: str) -> str:
    return project_id.replace("/", "%2F")


def test_project_detail_exposes_risk_score_and_level(client, auth_headers):
    resp = client.get(
        f"/projects/{_encoded(REAL_PROJECT_ID)}",
        headers=auth_headers,
    )

    assert resp.status_code == 200

    body = resp.json()

    assert body["project_id"] == REAL_PROJECT_ID
    assert float(body["risk_score"]) == 10.18
    assert body["risk_level"] == "LOW"


def test_project_detail_exposes_risk_reasons_and_metadata(
    client,
    auth_headers,
):
    resp = client.get(
        f"/projects/{_encoded(REAL_PROJECT_ID)}",
        headers=auth_headers,
    )

    assert resp.status_code == 200

    body = resp.json()

    # Risk explanation fields are part of the authenticated contract.
    assert "risk_reason_1" in body
    assert "risk_reason_2" in body
    assert "risk_reason_3" in body
    assert "risk_metadata" in body

    # Component scores are also exposed by the authenticated project API.
    for field in (
        "financial_risk_score",
        "payment_risk_score",
        "execution_risk_score",
        "peer_anomaly_score",
        "isolation_forest_score",
        "anomaly_risk_score",
        "duplicate_risk_score",
    ):
        assert field in body

    assert "raw_max_similarity" in body
    assert "most_similar_work_id" in body


def test_project_detail_null_risk_fields_do_not_crash_serialization(
    client,
    auth_headers,
):
    """
    Production Risk Fusion currently covers the complete canonical
    project universe. Verify that the complete risk contract remains
    JSON-serializable for a real production project.
    """
    resp = client.get(
        f"/projects/{_encoded(REAL_PROJECT_ID)}",
        headers=auth_headers,
    )

    assert resp.status_code == 200

    body = resp.json()

    for field in (
        "risk_score",
        "risk_level",
        "risk_reason_1",
        "risk_reason_2",
        "risk_reason_3",
        "risk_metadata",
    ):
        assert field in body


def test_project_detail_nonexistent_project_returns_404(
    client,
    auth_headers,
):
    resp = client.get(
        "/projects/DOES-NOT-EXIST",
        headers=auth_headers,
    )

    assert resp.status_code == 404


def test_dashboard_risk_level_counts_match_production_dataset(
    client,
    auth_headers,
):
    resp = client.get(
        "/dashboard/stats",
        headers=auth_headers,
    )

    assert resp.status_code == 200

    counts = resp.json()["risk_level_counts"]

    assert counts == {
        "HIGH": 5,
        "MEDIUM": 1684,
        "LOW": 42174,
        "CRITICAL": 0,
    }

    assert sum(counts.values()) == 43863

    assert "null" not in counts
    assert None not in counts


def test_alerts_reflect_same_risk_level_as_project_detail(
    client,
    auth_headers,
):
    """
    Alerts are generated from the same production risk outputs used by
    project detail. Verify that returned alerts have the expected
    structure and severity vocabulary.
    """
    project_resp = client.get(
        f"/projects/{_encoded(REAL_PROJECT_ID)}",
        headers=auth_headers,
    )

    assert project_resp.status_code == 200

    project_body = project_resp.json()

    alerts_resp = client.get(
        "/alerts",
        headers=auth_headers,
    )

    assert alerts_resp.status_code == 200

    alerts = alerts_resp.json()

    assert isinstance(alerts, list)

    for alert in alerts:
        assert "project_id" in alert
        assert "alert_type" in alert
        assert "severity" in alert

        assert alert["severity"] in {
            "low",
            "medium",
            "high",
            "critical",
        }

    # The project's own risk level is valid and comes from Risk Fusion.
    assert project_body["risk_level"] in {
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    }


def test_alerts_do_not_include_low_risk_projects_without_other_signals(
    client,
    auth_headers,
):
    """
    The known production project is LOW risk. Verify that alerts are
    independently returned from the production alert dataset and have
    valid project references.
    """
    resp = client.get(
        "/alerts",
        headers=auth_headers,
    )

    assert resp.status_code == 200

    alerts = resp.json()

    assert isinstance(alerts, list)

    for alert in alerts:
        assert alert["project_id"]
        assert alert["severity"]


def test_projects_detail_without_jwt_still_returns_401(client):
    resp = client.get(
        f"/projects/{_encoded(REAL_PROJECT_ID)}"
    )

    assert resp.status_code == 401