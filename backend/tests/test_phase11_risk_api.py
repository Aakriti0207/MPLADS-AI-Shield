"""Phase 11 FastAPI integration tests for the current Risk Fusion contract."""

from decimal import Decimal

from app.models import Project
from app.routes import projects


CURRENT_RISK = {
    "work_id": "WS/PHASE11/2024-2025/000001",
    "risk_score": 74.5,
    "risk_level": "HIGH",
    "evidence_status": "SUFFICIENT",
    "compliance_contribution": 20.0,
    "financial_anomaly_contribution": 12.5,
    "timeline_anomaly_contribution": 8.0,
    "duplicate_contribution": 4.0,
    "data_quality_contribution": 0.0,
    "payment_contribution": 6.0,
    "isolation_forest_contribution": 4.0,
    "total_evidence_signals": 5,
    "high_severity_signal_count": 2,
    "medium_severity_signal_count": 2,
    "low_severity_signal_count": 1,
    "has_compliance_signal": True,
    "has_financial_anomaly": True,
    "has_timeline_anomaly": True,
    "has_duplicate_signal": True,
    "has_data_quality_signal": False,
    "has_payment_signal": True,
    "has_isolation_forest_signal": True,
    "top_reason_1": "Payment activity is unusual relative to fitted history.",
    "top_reason_2": "A financial anomaly was detected against the peer baseline.",
    "top_reason_3": None,
    "risk_reasons": ["Payment activity is unusual relative to fitted history."],
    "source_signal_summary": {"signals": [{"source": "payment", "points": 6.0}]},
}


def _add_project(db_session, project_id=CURRENT_RISK["work_id"]):
    db_session.add(Project(project_id=project_id, is_synthetic=True, risk_score=Decimal("1.00"), risk_level="LOW"))
    db_session.commit()


def test_current_risk_endpoint_returns_complete_structured_contract(client, db_session, auth_headers, monkeypatch):
    _add_project(db_session)
    monkeypatch.setattr(projects, "get_risk_fusion_result", lambda work_id: CURRENT_RISK)

    response = client.get(f"/projects/{CURRENT_RISK['work_id'].replace('/', '%2F')}/risk", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert set(CURRENT_RISK).issubset(body)
    assert body["risk_score"] == 74.5
    assert body["payment_contribution"] == 6.0
    assert body["isolation_forest_contribution"] == 4.0
    assert isinstance(body["risk_reasons"], list)
    assert isinstance(body["source_signal_summary"], dict)


def test_insufficient_evidence_is_unassessed_not_low(client, db_session, auth_headers, monkeypatch):
    _add_project(db_session, "WS/PHASE11/2024-2025/000002")
    monkeypatch.setattr(projects, "get_risk_fusion_result", lambda work_id: {
        **CURRENT_RISK,
        "work_id": "WS/PHASE11/2024-2025/000002",
        "risk_score": 0.0,
        "risk_level": "UNASSESSED",
        "evidence_status": "INSUFFICIENT",
        "risk_reasons": [],
        "source_signal_summary": {"signals": []},
    })

    response = client.get("/projects/WS%2FPHASE11%2F2024-2025%2F000002/risk", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["risk_level"] == "UNASSESSED"
    assert response.json()["evidence_status"] == "INSUFFICIENT"


def test_risk_endpoint_requires_authentication(client, db_session):
    _add_project(db_session)
    response = client.get(f"/projects/{CURRENT_RISK['work_id'].replace('/', '%2F')}/risk")
    assert response.status_code == 401


def test_nonexistent_project_risk_returns_404(client, auth_headers):
    response = client.get("/projects/DOES%2FNOT%2FEXIST/risk", headers=auth_headers)
    assert response.status_code == 404


def test_legacy_project_endpoint_remains_available(client, db_session, auth_headers):
    _add_project(db_session)
    response = client.get(f"/projects/{CURRENT_RISK['work_id'].replace('/', '%2F')}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["risk_level"] == "LOW"