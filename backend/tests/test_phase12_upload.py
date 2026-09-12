"""Phase 12 upload-to-analysis coverage."""

from pathlib import Path

import pytest

from app.phase12_analysis import AnalysisInputError, analyze_csv


VALID_UPLOAD = (
    "project_id,state,category,sanction_amount,total_expenditure,recommended_date,sanction_date,completion_date\n"
    "P-001,Delhi,Road,500000,400000,2024-01-01,2024-01-15,2024-05-01\n"
    "P-002,Bihar,Bridge,300000,900000,2024-01-01,2024-02-01,2024-04-01\n"
)


def test_aliases_run_real_pipeline_and_return_results():
    result = analyze_csv(VALID_UPLOAD.encode(), "uploaded.csv")

    assert result["status"] == "success"
    assert result["summary"]["total_projects"] == 2
    assert len(result["projects"]) == 2
    assert {project["work_id"] for project in result["projects"]} == {"P-001", "P-002"}
    overspend = next(project for project in result["projects"] if project["work_id"] == "P-002")
    assert overspend["risk_score"] > 0
    assert "compliance" in overspend["evidence"]
    assert overspend["why_risky"]


@pytest.mark.parametrize(
    ("payload", "filename", "message"),
    [
        (b"", "empty.csv", "empty"),
        (b"state,amount\nDelhi,10\n", "missing.csv", "identifier"),
        (b"work_id,state\nP-1,Delhi\n", "data.txt", "Only .csv"),
    ],
)
def test_upload_validation_is_user_facing(payload, filename, message):
    with pytest.raises(AnalysisInputError, match=message):
        analyze_csv(payload, filename)


def test_analysis_does_not_write_production_outputs():
    processed = Path(__file__).parents[1] / "data" / "processed"
    protected = [
        processed / "canonical_projects.csv",
        processed / "ml_features.csv",
        processed / "project_risk_scores.csv",
    ]
    before = {path: path.stat().st_mtime_ns for path in protected if path.exists()}
    analyze_csv(VALID_UPLOAD.encode(), "uploaded.csv")
    after = {path: path.stat().st_mtime_ns for path in protected if path.exists()}
    assert after == before


def test_upload_endpoint_exposes_phase12_analysis(client, auth_headers):
    response = client.post(
        "/upload-analyze",
        headers=auth_headers,
        files={"file": ("uploaded.csv", VALID_UPLOAD, "text/csv")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["analysis"]["status"] == "success"
    assert body["analysis"]["summary"]["total_projects"] == 2
    assert len(body["analysis"]["projects"]) == 2