"""
Phase 7, Part A: GET /public/projects/{project_id}.

Added so the public Overview's "Recently Monitored Projects" list (and
the public /projects explorer) can open a project detail page without
requiring a session, without exposing AI risk information to anonymous
visitors, and without weakening the existing authenticated
GET /projects/{id} contract.
"""

from app.models import Project


def _seed_project(db_session, **overrides):
    defaults = dict(
        project_id="WS/PUBLIC/1",
        state="Bihar",
        constituency="Patna Sahib",
        work_type="Road construction",
        sanctioned_amount=500000,
        expenditure=250000,
        financial_progress=50,
        status="Active",
        risk_score=87.5,
        risk_level="CRITICAL",
        risk_reason_1="Expenditure exceeds sanctioned amount",
        mp_name="Test MP",
        is_synthetic=True,
    )
    defaults.update(overrides)
    project = Project(**defaults)
    db_session.add(project)
    db_session.commit()
    return project


def test_public_project_detail_returns_safe_fields_anonymously(client, db_session):
    _seed_project(db_session)

    resp = client.get("/public/projects/WS%2FPUBLIC%2F1")
    assert resp.status_code == 200
    body = resp.json()

    assert body["project_id"] == "WS/PUBLIC/1"
    assert body["state"] == "Bihar"
    assert body["constituency"] == "Patna Sahib"
    assert body["work_type"] == "Road construction"
    assert body["status"] == "Active"


def test_public_project_detail_never_exposes_risk_or_internal_fields(client, db_session):
    _seed_project(db_session)

    resp = client.get("/public/projects/WS%2FPUBLIC%2F1")
    assert resp.status_code == 200
    body = resp.json()

    # PublicProjectOut has no risk/internal columns at all -- this test
    # guards against a future edit accidentally widening that schema.
    for leaked_field in (
        "risk_score",
        "risk_level",
        "risk_reason_1",
        "risk_reason_2",
        "risk_reason_3",
        "risk_metadata",
        "mp_name",
    ):
        assert leaked_field not in body


def test_public_project_detail_404_for_unknown_id(client, db_session):
    resp = client.get("/public/projects/WS%2FDOES-NOT-EXIST%2F1")
    assert resp.status_code == 404


def test_authenticated_project_detail_still_requires_auth(client, db_session):
    """Confirms this change did not touch GET /projects/{id}'s existing
    authentication requirement."""
    _seed_project(db_session)
    resp = client.get("/projects/WS%2FPUBLIC%2F1")
    assert resp.status_code == 401


def test_authenticated_project_detail_still_includes_risk_for_real_users(client, db_session, auth_headers):
    _seed_project(db_session)
    resp = client.get("/projects/WS%2FPUBLIC%2F1", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_score"] is not None
    assert body["risk_level"] == "CRITICAL"


def test_public_overview_recent_projects_carry_a_usable_project_id(client, db_session):
    """The Overview page's click-through relies on recent_projects[].project_id
    being present and matching the id GET /public/projects/{id} accepts."""
    _seed_project(db_session)

    overview = client.get("/public/overview").json()
    assert overview["recent_projects"], "expected at least one recent project"
    project_id = overview["recent_projects"][0]["project_id"]

    encoded_id = project_id.replace("/", "%2F")
    detail = client.get(f"/public/projects/{encoded_id}")
    assert detail.status_code == 200
    assert detail.json()["project_id"] == project_id