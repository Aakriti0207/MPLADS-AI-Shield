"""
Tests for the anonymous, public-safe `/public/*` routes (app/routes/public.py).

No existing test file covered these routes at all before this one --
verified by grepping tests/ for "/public" (zero matches). This file
adds coverage for:

  1. `GET /public/projects/{project_id}` (new -- added to fix the
     Overview "Recently Monitored Projects" click-through bug): safe
     fields returned, no risk/internal leakage, 404 for an unknown id,
     no authentication required.
  2. That the pre-existing, still-protected `GET /projects/{id}` is
     completely unaffected by the new public route (still 401s an
     anonymous caller, still 200s an authenticated one, still returns
     the full ProjectOut including risk fields).

Uses the same `client` / `db_session` / `auth_headers` fixtures as the
rest of the suite (see conftest.py).
"""

from decimal import Decimal
from datetime import date

from app.models import Project


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


# --- GET /public/projects/{id}: happy path ---------------------------------

def test_public_project_detail_is_reachable_without_auth(client, db_session):
    _make_project(db_session)
    resp = client.get(f"/public/projects/{_encoded('WS/PUB/2024/000001')}")
    assert resp.status_code == 200


def test_public_project_detail_returns_safe_fields(client, db_session):
    _make_project(db_session)
    resp = client.get(f"/public/projects/{_encoded('WS/PUB/2024/000001')}")
    body = resp.json()
    assert body["project_id"] == "WS/PUB/2024/000001"
    assert body["state"] == "Delhi"
    assert body["constituency"] == "New Delhi"
    assert body["work_type"] == "Road"
    assert body["status"] == "Ongoing"
    assert Decimal(str(body["sanctioned_amount"])) == Decimal("500000.00")
    assert Decimal(str(body["expenditure"])) == Decimal("400000.00")
    assert Decimal(str(body["financial_progress"])) == Decimal("80.00")


def test_public_project_detail_includes_district_mp_agency_and_dates_when_present(client, db_session):
    """These were missing from PublicProjectOut entirely (not just null) until
    this fix, so the public Project Detail page showed "Not available" for
    them even when the backend had real data. They're already-public MPLADS
    fields -- not risk/internal data -- so the endpoint should surface them
    whenever the underlying project row has them."""
    _make_project(
        db_session,
        district="North Delhi",
        sanction_date=date(2023, 4, 1),
        start_date=date(2023, 5, 15),
        expected_completion=date(2024, 3, 31),
        actual_completion=None,
    )
    resp = client.get(f"/public/projects/{_encoded('WS/PUB/2024/000001')}")
    body = resp.json()
    assert body["district"] == "North Delhi"
    assert body["mp_name"] == "Test MP"
    assert body["implementing_agency"] is None  # not set on this fixture, but the key exists
    assert "implementing_agency" in body
    assert body["sanction_date"] == "2023-04-01"
    assert body["start_date"] == "2023-05-15"
    assert body["expected_completion"] == "2024-03-31"
    assert body["actual_completion"] is None


def test_public_project_detail_never_exposes_risk_or_internal_fields(client, db_session):
    _make_project(db_session)
    resp = client.get(f"/public/projects/{_encoded('WS/PUB/2024/000001')}")
    body = resp.json()
    forbidden_keys = {
        "risk_score", "risk_level",
        "risk_reason_1", "risk_reason_2", "risk_reason_3",
        "risk_metadata",
        "financial_risk_score", "payment_risk_score",
        "execution_risk_score", "anomaly_risk_score", "duplicate_risk_score",
    }
    assert forbidden_keys.isdisjoint(body.keys())
    # Belt-and-suspenders: none of the actual risk values leaked into the
    # response body as a string anywhere either.
    assert "flagged for internal audit" not in resp.text
    assert "CRITICAL" not in resp.text


def test_public_project_detail_matches_the_public_list_fields(client, db_session):
    """The list endpoint (`GET /public/projects`) and this detail endpoint
    both use PublicProjectOut -- their field sets for the same project
    must be identical, since the detail route exists purely to let the
    Overview page open a link to a project it already saw in a public,
    sanitized list/aggregate response."""
    _make_project(db_session)
    list_resp = client.get("/public/projects")
    detail_resp = client.get(f"/public/projects/{_encoded('WS/PUB/2024/000001')}")
    list_item = next(p for p in list_resp.json()["items"] if p["project_id"] == "WS/PUB/2024/000001")
    assert set(list_item.keys()) == set(detail_resp.json().keys())


# --- GET /public/projects/{id}: not found -----------------------------------

def test_public_project_detail_404_for_unknown_id(client, db_session):
    resp = client.get(f"/public/projects/{_encoded('WS/DOES/NOT/EXIST')}")
    assert resp.status_code == 404


# --- The protected route is unchanged ---------------------------------------

def test_protected_project_detail_still_requires_auth(client, db_session):
    _make_project(db_session)
    resp = client.get(f"/projects/{_encoded('WS/PUB/2024/000001')}")
    assert resp.status_code == 401


def test_protected_project_detail_still_returns_full_fields_when_authenticated(client, db_session, auth_headers):
    _make_project(db_session)
    resp = client.get(f"/projects/{_encoded('WS/PUB/2024/000001')}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    # The full authenticated contract still includes risk fields --
    # confirming the new public route didn't touch this one at all.
    assert Decimal(str(body["risk_score"])) == Decimal("87.50")
    assert body["risk_level"] == "CRITICAL"


def _encoded(project_id: str) -> str:
    from urllib.parse import quote
    return quote(project_id, safe="")