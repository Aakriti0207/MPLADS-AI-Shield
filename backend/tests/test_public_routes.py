"""
Tests for anonymous public project routes and the protected project route.

The public routes are tested against the test database because they are
designed to expose the public/sanitized project representation.

The authenticated /projects/{id} route is tested against the production
canonical dataset because the current project API uses canonical_projects.csv
and project_risk_scores.csv as its source of truth.
"""

from decimal import Decimal
from datetime import date
from urllib.parse import quote

from app.models import Project


REAL_PROJECT_ID = "WS/MP1/2023-2024/103702"


def _make_project(db_session, **overrides):
    defaults = dict(
        project_id="WS/PUB/2024/000001",
        state="Delhi",
        constituency="New Delhi",
        mp_name="Test MP",
        work_type="Road",
        sanctioned_amount=Decimal("500000.00"),
        expenditure=Decimal("400000.00"),
        financial_progress=Decimal("80.00"),
        status="Ongoing",
        risk_score=Decimal("87.50"),
        risk_level="CRITICAL",
        risk_reason_1="Expenditure exceeds sanctioned amount",
        risk_reason_2="Duplicate work order suspected",
        risk_metadata={"reviewer_notes": "flagged for internal audit"},
        is_synthetic=True,
    )

    defaults.update(overrides)

    project = Project(**defaults)
    db_session.add(project)
    db_session.commit()

    return project


def _encoded(project_id: str) -> str:
    return quote(project_id, safe="")


# ---------------------------------------------------------------------------
# GET /public/projects/{id}
# ---------------------------------------------------------------------------

def test_public_project_detail_is_reachable_without_auth(client, db_session):
    _make_project(db_session)

    resp = client.get(
        f"/public/projects/{_encoded('WS/PUB/2024/000001')}"
    )

    assert resp.status_code == 200


def test_public_project_detail_returns_safe_fields(client, db_session):
    _make_project(db_session)

    resp = client.get(
        f"/public/projects/{_encoded('WS/PUB/2024/000001')}"
    )

    assert resp.status_code == 200

    body = resp.json()

    assert body["project_id"] == "WS/PUB/2024/000001"
    assert body["state"] == "Delhi"
    assert body["constituency"] == "New Delhi"
    assert body["work_type"] == "Road"
    assert body["status"] == "Ongoing"

    assert Decimal(str(body["sanctioned_amount"])) == Decimal("500000.00")
    assert Decimal(str(body["expenditure"])) == Decimal("400000.00")
    assert Decimal(str(body["financial_progress"])) == Decimal("80.00")


def test_public_project_detail_includes_district_mp_agency_and_dates_when_present(
    client,
    db_session,
):
    _make_project(
        db_session,
        district="North Delhi",
        sanction_date=date(2023, 4, 1),
        start_date=date(2023, 5, 15),
        expected_completion=date(2024, 3, 31),
        actual_completion=None,
    )

    resp = client.get(
        f"/public/projects/{_encoded('WS/PUB/2024/000001')}"
    )

    assert resp.status_code == 200

    body = resp.json()

    assert body["district"] == "North Delhi"
    assert body["mp_name"] == "Test MP"
    assert body["implementing_agency"] is None
    assert "implementing_agency" in body

    assert body["sanction_date"] == "2023-04-01"
    assert body["start_date"] == "2023-05-15"
    assert body["expected_completion"] == "2024-03-31"
    assert body["actual_completion"] is None


def test_public_project_detail_never_exposes_risk_or_internal_fields(
    client,
    db_session,
):
    _make_project(db_session)

    resp = client.get(
        f"/public/projects/{_encoded('WS/PUB/2024/000001')}"
    )

    assert resp.status_code == 200

    body = resp.json()

    forbidden_keys = {
        "risk_score",
        "risk_level",
        "risk_reason_1",
        "risk_reason_2",
        "risk_reason_3",
        "risk_metadata",
        "financial_risk_score",
        "payment_risk_score",
        "execution_risk_score",
        "anomaly_risk_score",
        "duplicate_risk_score",
    }

    assert forbidden_keys.isdisjoint(body.keys())

    assert "flagged for internal audit" not in resp.text
    assert "CRITICAL" not in resp.text


def test_public_project_detail_matches_the_public_list_fields(
    client,
    db_session,
):
    _make_project(db_session)

    list_resp = client.get("/public/projects")

    detail_resp = client.get(
        f"/public/projects/{_encoded('WS/PUB/2024/000001')}"
    )

    assert list_resp.status_code == 200
    assert detail_resp.status_code == 200

    list_item = next(
        p
        for p in list_resp.json()["items"]
        if p["project_id"] == "WS/PUB/2024/000001"
    )

    assert set(list_item.keys()) == set(detail_resp.json().keys())


def test_public_project_detail_404_for_unknown_id(client, db_session):
    resp = client.get(
        f"/public/projects/{_encoded('WS/DOES/NOT/EXIST')}"
    )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Protected /projects/{id}
# ---------------------------------------------------------------------------

def test_protected_project_detail_still_requires_auth(client, db_session):
    _make_project(db_session)

    resp = client.get(
        f"/projects/{_encoded('WS/PUB/2024/000001')}"
    )

    assert resp.status_code == 401


def test_protected_project_detail_uses_production_risk_dataset_when_authenticated(
    client,
    auth_headers,
):
    """
    The authenticated project route no longer reads synthetic DB-only
    projects. It uses the canonical production project universe plus
    Risk Fusion output.
    """
    resp = client.get(
        f"/projects/{_encoded(REAL_PROJECT_ID)}",
        headers=auth_headers,
    )

    assert resp.status_code == 200

    body = resp.json()

    assert body["project_id"] == REAL_PROJECT_ID

    assert Decimal(str(body["risk_score"])) == Decimal("10.18")
    assert body["risk_level"] == "LOW"