"""
Tests for the Map coordinate fix (Phase 2).

Root cause that was fixed: `_canonical_row_to_project()` in
app/routes/projects.py hardcoded `latitude=None, longitude=None` for
every project, on every surface (real, public, demo), so the Map
feature could never plot anything.

What these tests cover
-----------------------
  1. `app.geo_centroids.resolve_coordinates` itself: exact district
     match, state-centroid fallback for an unmatched district, and the
     "don't fabricate it" None/None/None case for an unresolvable
     state -- see requirement #4 in the Phase 2 brief.
  2. The protected `/projects` and `/projects/{id}` endpoints now
     return coordinates + `location_precision` for a known real
     project.
  3. The demo endpoints (`/demo/projects/{id}`) return the SAME
     coordinates as the protected endpoint for the same project --
     requirement #6 (real/public/demo consistency).
  4. The public endpoints (`/public/projects`, `/public/projects/{id}`,
     `/public/overview`'s `recent_projects`) now carry coordinates too
     (they previously had no coordinate fields on the response schema
     at all), including the state-centroid fallback case.
  5. RBAC scope filtering is unaffected by the coordinate fix -- a
     scoped account still only sees its own jurisdiction's projects,
     which now also carry coordinates.

`WS/MP1/2023-2024/103702` (Bihar / Samastipur) is the same real
project ID already used by tests/test_project_api.py and
tests/test_public_project_detail.py, and its (state, district) is a
confirmed exact match in data/geo/district_centroids.csv (see
data/geo/SOURCE.md), so its expected precision is always
"district_centroid".
"""

import urllib.parse

import pytest

from app.geo_centroids import resolve_coordinates
from app.models import Project
from tests.conftest import make_scoped_headers


REAL_PROJECT_ID = "WS/MP1/2023-2024/103702"
REAL_PROJECT_STATE = "Bihar"
REAL_PROJECT_DISTRICT = "Samastipur"


def _encode(work_id: str) -> str:
    return urllib.parse.quote(work_id, safe="")


def _seed_project(db_session, **overrides):
    defaults = dict(
        project_id="WS/PUBLIC/COORD/1",
        state="Bihar",
        district="Samastipur",
        constituency="Patna Sahib",
        work_type="Road construction",
        sanctioned_amount=500000,
        expenditure=250000,
        financial_progress=50,
        status="Active",
        mp_name="Test MP",
        is_synthetic=True,
    )
    defaults.update(overrides)
    project = Project(**defaults)
    db_session.add(project)
    db_session.commit()
    return project


# ---------------------------------------------------------------------
# 1. app.geo_centroids.resolve_coordinates -- unit level
# ---------------------------------------------------------------------

def test_resolve_coordinates_matches_known_district():
    lat, lon, precision = resolve_coordinates(
        REAL_PROJECT_STATE, REAL_PROJECT_DISTRICT
    )
    assert precision == "district_centroid"
    assert lat is not None and lon is not None
    # Sanity: within India's approximate bounding box, not just "a number".
    assert 6 < float(lat) < 36
    assert 68 < float(lon) < 98


def test_resolve_coordinates_falls_back_to_state_centroid_for_unmatched_district():
    # "Banas Kantha" (as spelled in canonical_projects.csv) is not an
    # exact normalized match in data/geo/district_centroids.csv (which
    # spells it "Banaskantha") -- confirmed at the time this file was
    # written (see data/geo/SOURCE.md's coverage note). This exercises
    # the state-centroid fallback path instead of hardcoding a lat/lon.
    lat, lon, precision = resolve_coordinates("Gujarat", "Banas Kantha")
    assert precision == "state_centroid"
    assert lat is not None and lon is not None

    # The state centroid must be internally consistent: it's the same
    # value resolve_coordinates() would give for a state with no
    # district at all.
    state_lat, state_lon, state_precision = resolve_coordinates(
        "Gujarat", None
    )
    assert state_precision == "state_centroid"
    assert (lat, lon) == (state_lat, state_lon)


def test_resolve_coordinates_never_fabricates_an_unresolvable_location():
    lat, lon, precision = resolve_coordinates(
        "Not A Real State", "Not A Real District"
    )
    assert (lat, lon, precision) == (None, None, None)


def test_resolve_coordinates_handles_missing_state_and_district():
    assert resolve_coordinates(None, None) == (None, None, None)
    assert resolve_coordinates(None, "Samastipur") == (None, None, None)


def test_resolve_coordinates_is_normalization_insensitive():
    """Case/whitespace/'&' formatting differences should not break a
    match that would otherwise succeed."""
    exact = resolve_coordinates("Bihar", "Samastipur")
    messy = resolve_coordinates("  bihar  ", "SAMASTIPUR")
    assert exact == messy


# ---------------------------------------------------------------------
# 2. Protected /projects and /projects/{id}
# ---------------------------------------------------------------------

def test_project_detail_returns_district_centroid(client, auth_headers):
    response = client.get(
        f"/projects/{_encode(REAL_PROJECT_ID)}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()

    assert body["latitude"] is not None
    assert body["longitude"] is not None
    assert body["location_precision"] == "district_centroid"

    expected_lat, expected_lon, _ = resolve_coordinates(
        REAL_PROJECT_STATE, REAL_PROJECT_DISTRICT
    )
    assert float(body["latitude"]) == pytest.approx(float(expected_lat))
    assert float(body["longitude"]) == pytest.approx(float(expected_lon))


def test_projects_list_coordinates_are_internally_consistent(
    client, auth_headers
):
    """Every row's (latitude, longitude, location_precision) must agree
    on whether a location was resolved -- never a partial pair, and
    never a precision label with no actual coordinate."""
    response = client.get(
        "/projects?skip=0&limit=50",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0

    resolved_count = 0
    for project in data:
        has_lat = project["latitude"] is not None
        has_lon = project["longitude"] is not None
        has_precision = project["location_precision"] is not None
        assert has_lat == has_lon == has_precision
        if has_precision:
            assert project["location_precision"] in (
                "district_centroid",
                "state_centroid",
            )
            assert 6 < float(project["latitude"]) < 36
            assert 68 < float(project["longitude"]) < 98
            resolved_count += 1

    # Every one of the 35 canonical states resolves to at least a
    # state centroid (see data/geo/SOURCE.md), so a real page should
    # never come back with zero resolved rows.
    assert resolved_count > 0


# ---------------------------------------------------------------------
# 3. Demo endpoints match the protected endpoint (requirement #6)
# ---------------------------------------------------------------------

def test_demo_project_detail_matches_protected_project_coordinates(
    client, auth_headers
):
    protected = client.get(
        f"/projects/{_encode(REAL_PROJECT_ID)}",
        headers=auth_headers,
    )
    demo = client.get(f"/demo/projects/{_encode(REAL_PROJECT_ID)}")

    assert protected.status_code == 200
    assert demo.status_code == 200

    protected_body = protected.json()
    demo_body = demo.json()

    assert demo_body["location_precision"] == protected_body["location_precision"]
    assert float(demo_body["latitude"]) == pytest.approx(
        float(protected_body["latitude"])
    )
    assert float(demo_body["longitude"]) == pytest.approx(
        float(protected_body["longitude"])
    )


def test_demo_projects_list_has_consistent_coordinates(client):
    """No auth required for demo (see lib/demoSession.js on the
    frontend side -- demo sessions carry no JWT)."""
    response = client.get("/demo/projects?skip=0&limit=20")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    for project in data:
        has_lat = project["latitude"] is not None
        has_lon = project["longitude"] is not None
        has_precision = project["location_precision"] is not None
        assert has_lat == has_lon == has_precision


# ---------------------------------------------------------------------
# 4. Public endpoints now carry coordinates (previously no field at all)
# ---------------------------------------------------------------------

def test_public_project_detail_includes_district_centroid(db_session, client):
    _seed_project(db_session)
    response = client.get("/public/projects/WS%2FPUBLIC%2FCOORD%2F1")
    assert response.status_code == 200
    body = response.json()

    assert body["location_precision"] == "district_centroid"
    expected_lat, expected_lon, _ = resolve_coordinates("Bihar", "Samastipur")
    assert float(body["latitude"]) == pytest.approx(float(expected_lat))
    assert float(body["longitude"]) == pytest.approx(float(expected_lon))


def test_public_project_list_includes_coordinates(db_session, client):
    _seed_project(db_session)
    response = client.get("/public/projects")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) > 0
    assert items[0]["location_precision"] == "district_centroid"
    assert items[0]["latitude"] is not None


def test_public_project_with_unmatched_district_gets_state_centroid(
    db_session, client
):
    _seed_project(
        db_session,
        project_id="WS/PUBLIC/COORD/2",
        state="Gujarat",
        district="Banas Kantha",
    )
    response = client.get("/public/projects/WS%2FPUBLIC%2FCOORD%2F2")
    assert response.status_code == 200
    body = response.json()

    assert body["location_precision"] == "state_centroid"
    expected_lat, expected_lon, _ = resolve_coordinates(
        "Gujarat", "Banas Kantha"
    )
    assert float(body["latitude"]) == pytest.approx(float(expected_lat))
    assert float(body["longitude"]) == pytest.approx(float(expected_lon))


def test_public_project_with_no_state_gets_no_coordinates(db_session, client):
    _seed_project(
        db_session,
        project_id="WS/PUBLIC/COORD/3",
        state=None,
        district=None,
    )
    response = client.get("/public/projects/WS%2FPUBLIC%2FCOORD%2F3")
    assert response.status_code == 200
    body = response.json()

    assert body["latitude"] is None
    assert body["longitude"] is None
    assert body["location_precision"] is None


def test_public_overview_recent_projects_include_coordinates(db_session, client):
    _seed_project(db_session)
    response = client.get("/public/overview")
    assert response.status_code == 200
    recent = response.json()["recent_projects"]
    assert recent
    assert recent[0]["location_precision"] == "district_centroid"
    assert recent[0]["latitude"] is not None


def test_public_project_response_never_exposes_risk_fields_alongside_coordinates(
    db_session, client
):
    """Guard against the coordinate fix accidentally widening the public
    contract -- it must add ONLY latitude/longitude/location_precision,
    nothing risk-related (see app/routes/public.py's module docstring)."""
    _seed_project(db_session)
    response = client.get("/public/projects/WS%2FPUBLIC%2FCOORD%2F1")
    body = response.json()
    for leaked_field in (
        "risk_score",
        "risk_level",
        "risk_reason_1",
        "risk_metadata",
    ):
        assert leaked_field not in body


# ---------------------------------------------------------------------
# 5. RBAC scope filtering is unaffected by the coordinate fix
# ---------------------------------------------------------------------

def test_district_scoped_account_sees_only_its_own_district_with_coordinates(
    client, db_session
):
    headers = make_scoped_headers(
        client,
        db_session,
        email="district.coords@example.gov.in",
        role="District Authority",
        scope_state=REAL_PROJECT_STATE,
        scope_district=REAL_PROJECT_DISTRICT,
    )

    response = client.get("/projects/query?limit=25", headers=headers)
    assert response.status_code == 200
    body = response.json()

    assert body["total"] > 0
    for project in body["items"]:
        # Scope is preserved: every row really is this district.
        # Compare case-insensitively: canonical_projects.csv stores the
        # district upper-cased ("SAMASTIPUR") and the API deliberately
        # returns the source string unchanged (see app/geo_centroids.py),
        # while the scope filter itself is already case-insensitive.
        assert project["state"].casefold() == REAL_PROJECT_STATE.casefold()
        assert (
            project["district"].casefold()
            == REAL_PROJECT_DISTRICT.casefold()
        )
        # And it now also carries the same resolved coordinate.
        assert project["location_precision"] == "district_centroid"


def test_out_of_scope_project_detail_still_404s_after_coordinate_fix(
    client, db_session
):
    """The coordinate fix must not change RBAC's existing 403-vs-404
    behaviour (app/routes/projects.py's module docstring): an
    out-of-scope project id still returns the same 404 as a
    non-existent one."""
    headers = make_scoped_headers(
        client,
        db_session,
        email="district.other@example.gov.in",
        role="District Authority",
        scope_state="Kerala",
        scope_district="Kollam",
    )
    response = client.get(
        f"/projects/{_encode(REAL_PROJECT_ID)}",
        headers=headers,
    )
    assert response.status_code == 404