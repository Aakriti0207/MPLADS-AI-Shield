"""
Phase 7 QA: GET /projects and GET /projects/{project_id} -- pagination
edge cases, deterministic ordering, and 404 behavior. Basic auth-gate
coverage for these routes already exists in test_protected_routes.py
and is not duplicated here.
"""

import csv
from decimal import Decimal
from pathlib import Path

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


def test_project_list_and_detail_preserve_project_fields(client, db_session, auth_headers):
    db_session.add(Project(
        project_id="WS/CORE/1",
        state="Kerala",
        district="Ernakulam",
        constituency="Kochi",
        mp_name="Example MP",
        elected_nominated="Elected MP",
        work_type="Road",
        status="Ongoing",
        sanctioned_amount=Decimal("100000.00"),
        expenditure=Decimal("25000.00"),
        financial_progress=Decimal("25.00"),
        is_synthetic=True,
    ))
    db_session.commit()

    listed = client.get("/projects?limit=10", headers=auth_headers)
    detailed = client.get("/projects/WS%2FCORE%2F1", headers=auth_headers)
    assert listed.status_code == detailed.status_code == 200
    list_project = next(row for row in listed.json() if row["project_id"] == "WS/CORE/1")
    detail_project = detailed.json()
    for field in (
        "state", "district", "constituency", "mp_name", "elected_nominated",
        "work_type", "status", "sanctioned_amount", "expenditure",
        "financial_progress",
    ):
        assert list_project[field] == detail_project[field]


def test_projects_query_filters_without_changing_project_fields(client, db_session, auth_headers):
    db_session.add_all([
        Project(
            project_id="WS/QUERY/1", state="Kerala", district="Ernakulam",
            work_type="Road", status="Ongoing", risk_level="HIGH",
            expenditure=Decimal("10.00"), is_synthetic=True,
        ),
        Project(
            project_id="WS/QUERY/2", state="Kerala", district="Kottayam",
            work_type="School", status="Completed", risk_level="LOW",
            expenditure=Decimal("20.00"), is_synthetic=True,
        ),
    ])
    db_session.commit()

    response = client.get(
        "/projects/query?state=Kerala&district=Ernakulam&category=Road&status=Ongoing&risk_level=HIGH",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()[0]["project_id"] == "WS/QUERY/1"
    assert response.json()[0]["expenditure"] == "10.00"


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


def test_project_risk_route_reads_phase9_output_and_uses_project_id_match(client, db_session, auth_headers):
    project = Project(project_id="WS/MP1/2024-2025/101", state="Test State", is_synthetic=True)
    db_session.add(project)
    db_session.commit()

    csv_path = Path(__file__).resolve().parent.parent / "data" / "processed" / "project_risk_scores.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "work_id",
                "risk_score",
                "risk_level",
                "evidence_status",
                "compliance_contribution",
                "financial_anomaly_contribution",
                "timeline_anomaly_contribution",
                "duplicate_contribution",
                "data_quality_contribution",
                "payment_contribution",
                "isolation_forest_contribution",
                "top_reason_1",
                "top_reason_2",
                "top_reason_3",
                "risk_reasons",
                "source_signal_summary",
            ],
        )
        writer.writeheader()
        writer.writerow({
            "work_id": "WS/MP1/2024-2025/101",
            "risk_score": "72.5",
            "risk_level": "HIGH",
            "evidence_status": "SUFFICIENT",
            "compliance_contribution": "16.0",
            "financial_anomaly_contribution": "10.0",
            "timeline_anomaly_contribution": "6.0",
            "duplicate_contribution": "4.0",
            "data_quality_contribution": "0.0",
            "payment_contribution": "5.0",
            "isolation_forest_contribution": "5.0",
            "top_reason_1": "Expenditure exceeds sanction.",
            "top_reason_2": "Large anomaly in payment timing.",
            "top_reason_3": "Duplicate description match found.",
            "risk_reasons": '["Expenditure exceeds sanction.", "Large anomaly in payment timing."]',
            "source_signal_summary": '{"signals": [{"source": "compliance", "identifier": "C08", "severity_tier": 3, "points": 16.0}]}',
        })

    resp = client.get("/projects/WS%2FMP1%2F2024-2025%2F101/risk", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["project_id"] == "WS/MP1/2024-2025/101"
    assert body["risk_score"] == 72.5
    assert body["risk_level"] == "HIGH"
    assert body["evidence_status"] == "SUFFICIENT"
    assert body["reason_count"] == 2
    assert body["reasons"][0] == "Expenditure exceeds sanction."


def test_project_risk_route_missing_project_returns_404(client, auth_headers):
    resp = client.get("/projects/WS%2FMP9%2F2024-2025%2F999/risk", headers=auth_headers)
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()