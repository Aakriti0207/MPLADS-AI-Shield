"""Phase 11 FastAPI integration tests for the current Risk Fusion contract."""

def test_current_risk_endpoint_returns_complete_structured_contract(client, auth_headers):
    # Use a real project from the current canonical/Risk Fusion dataset.
    project_id = "WS/MP1/2023-2024/103702"
    encoded_id = project_id.replace("/", "%2F")

    response = client.get(
        f"/projects/{encoded_id}/risk",
        headers=auth_headers,
    )

    assert response.status_code == 200

    body = response.json()

    # Current Risk Fusion contract.
    assert body["work_id"] == project_id
    assert "risk_score" in body
    assert "risk_level" in body
    assert "evidence_status" in body

    assert body["risk_level"] in {"LOW", "MEDIUM", "HIGH", "UNASSESSED"}
    assert body["evidence_status"] in {"SUFFICIENT", "INSUFFICIENT"}

    # Risk Fusion currently provides these structured fields.
    assert "payment_contribution" in body
    assert "isolation_forest_contribution" in body
    assert "risk_reasons" in body
    assert "source_signal_summary" in body

    assert isinstance(body["risk_reasons"], list)
    assert isinstance(body["source_signal_summary"], dict)


def test_risk_endpoint_requires_authentication(client):
    project_id = "WS/MP1/2023-2024/103702"
    encoded_id = project_id.replace("/", "%2F")

    response = client.get(f"/projects/{encoded_id}/risk")

    assert response.status_code == 401


def test_nonexistent_project_risk_returns_404(client, auth_headers):
    response = client.get(
        "/projects/DOES%2FNOT%2FEXIST/risk",
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_real_project_risk_matches_current_risk_fusion_output(client, auth_headers):
    project_id = "WS/MP1/2023-2024/103702"
    encoded_id = project_id.replace("/", "%2F")

    response = client.get(
        f"/projects/{encoded_id}/risk",
        headers=auth_headers,
    )

    assert response.status_code == 200

    body = response.json()

    # Values verified from the current production Risk Fusion output.
    assert body["risk_score"] == 10.18
    assert body["risk_level"] == "LOW"
    assert body["evidence_status"] == "SUFFICIENT"


def test_project_endpoint_uses_current_canonical_dataset(client, auth_headers):
    project_id = "WS/MP1/2023-2024/103702"
    encoded_id = project_id.replace("/", "%2F")

    response = client.get(
        f"/projects/{encoded_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["project_id"] == project_id
    assert body["risk_level"] == "LOW"
    assert body["risk_score"] == 10.18
