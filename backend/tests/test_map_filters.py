"""
Tests for Phase 4: Map filters and search.

What changed on the backend, and what these tests pin down
-----------------------------------------------------------
  1. `risk_level` is a real server-side filter on `/projects/query` and
     `/demo/projects/query`. Risk is a Risk Fusion overlay, not a column
     of the canonical frame, so it used to be filterable only in the
     browser -- over one small page of an unfiltered list. Only 5 of the
     43,863 projects are HIGH, so a client-side filter would almost never
     find them. Server-side, it is applied on top of the RBAC scope, so it
     can only ever narrow what a caller may see.
  2. `/demo/projects/query` gained `district` and `constituency`.
  3. `/projects/filter-options` accepts optional `state` / `district` so
     the district and constituency lists cascade; with no parameters the
     response is unchanged.
  4. `/demo/projects/filter-options` is new. Demo sessions carry no JWT,
     so they could not use the protected endpoint at all.
  5. `/public/projects` gained `district` / `constituency` filters and
     district search, so the shared frontend query builder never has a
     filter silently dropped by one of the three API surfaces.

Expected values are derived from the real canonical / Risk Fusion frames
at test time rather than hardcoded, so they follow the data.
"""

import urllib.parse

import pytest

from app.models import Project
from tests.conftest import make_scoped_headers


REAL_PROJECT_ID = "WS/MP1/2023-2024/103702"
REAL_STATE = "Bihar"
REAL_DISTRICT = "Samastipur"


def _q(value: str) -> str:
    return urllib.parse.quote(value, safe="")


def _fold(value) -> str:
    return str(value if value is not None else "").strip().casefold()


# ---------------------------------------------------------------------
# Real data helpers
# ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def canonical():
    """The exact master frame the project endpoints filter.

    Not app.aggregations.load_canonical_projects() on its own: the API
    layer merges constituency_resolution.csv on top of it (see
    _build_project_datasets), so the project-location `constituency` the
    filters, search and option lists use can differ from the raw column.
    """
    from app.routes.projects import _load_project_datasets

    return _load_project_datasets()[0]


@pytest.fixture(scope="module")
def risk_levels():
    """work_id -> UPPER-CASE Risk Fusion level."""
    from app.aggregations import load_risk_fusion

    risk_df = load_risk_fusion()
    return {
        str(work_id).strip(): str(level).strip().upper()
        for work_id, level in zip(risk_df["work_id"], risk_df["risk_level"])
    }


def _expected_ids(canonical, risk_levels, *, state=None, district=None,
                  constituency=None, risk=None):
    frame = canonical
    for column, value in (
        ("state", state),
        ("district", district),
        ("constituency", constituency),
    ):
        if value:
            frame = frame[frame[column].map(_fold) == _fold(value)]
    ids = [str(w).strip() for w in frame["work_id"]]
    if risk:
        ids = [w for w in ids if risk_levels.get(w) == risk.upper()]
    return set(ids)


def _all_pages(client, path, params, headers=None, page_size=300):
    """Walk every page of a query endpoint and return all project IDs."""
    ids, skip = [], 0
    while True:
        query = urllib.parse.urlencode({**params, "skip": skip, "limit": page_size})
        resp = client.get(f"{path}?{query}", headers=headers or {})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        ids.extend(item["project_id"] for item in body["items"])
        skip += page_size
        if skip >= body["total"]:
            return ids, body["total"]


@pytest.fixture()
def a_medium_project(canonical, risk_levels):
    """A real MEDIUM-risk project with a state, district and constituency."""
    frame = canonical[
        canonical["state"].notna()
        & canonical["district"].notna()
        & canonical["constituency"].notna()
    ]
    for _, row in frame.iterrows():
        work_id = str(row["work_id"]).strip()
        if risk_levels.get(work_id) == "MEDIUM":
            return {
                "work_id": work_id,
                "state": str(row["state"]).strip(),
                "district": str(row["district"]).strip(),
                "constituency": str(row["constituency"]).strip(),
            }
    pytest.skip("no MEDIUM-risk project with full location in the dataset")


# =====================================================================
# 1. risk_level on /projects/query (authenticated)
# =====================================================================

def test_risk_level_filter_returns_only_that_level(client, auth_headers, canonical, risk_levels):
    ids, total = _all_pages(client, "/projects/query", {"risk_level": "HIGH"}, auth_headers)
    expected = _expected_ids(canonical, risk_levels, risk="HIGH")
    assert total == len(expected) > 0
    assert set(ids) == expected


def test_risk_level_filter_is_case_insensitive(client, auth_headers):
    upper = client.get("/projects/query?risk_level=HIGH&limit=50", headers=auth_headers).json()
    lower = client.get("/projects/query?risk_level=high&limit=50", headers=auth_headers).json()
    assert upper["total"] == lower["total"] > 0
    assert all(item["risk_level"] == "HIGH" for item in lower["items"])


def test_risk_level_all_or_blank_means_no_filter(client, auth_headers):
    plain = client.get("/projects/query?limit=1", headers=auth_headers).json()["total"]
    for value in ("All", "all", ""):
        resp = client.get(f"/projects/query?limit=1&risk_level={value}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == plain


def test_unknown_risk_level_is_rejected_not_ignored(client, auth_headers):
    resp = client.get("/projects/query?risk_level=SEVERE", headers=auth_headers)
    assert resp.status_code == 422
    assert "risk_level" in resp.json()["detail"]


def test_risk_level_with_no_matches_returns_empty_page(client, auth_headers, risk_levels):
    """CRITICAL is a valid level the current data simply has no rows for."""
    if "CRITICAL" in set(risk_levels.values()):
        pytest.skip("dataset now contains CRITICAL rows")
    body = client.get("/projects/query?risk_level=CRITICAL", headers=auth_headers).json()
    assert body["total"] == 0
    assert body["items"] == []


def test_risk_level_is_part_of_the_page_cache_key(client, auth_headers):
    """Same everything-else, different level: must not be served from the
    other level's cached page."""
    high = client.get("/projects/query?limit=5&risk_level=HIGH", headers=auth_headers).json()
    medium = client.get("/projects/query?limit=5&risk_level=MEDIUM", headers=auth_headers).json()
    assert {i["risk_level"] for i in high["items"]} == {"HIGH"}
    assert {i["risk_level"] for i in medium["items"]} == {"MEDIUM"}
    assert high["total"] != medium["total"]


def test_location_and_risk_filters_combine(client, auth_headers, a_medium_project, canonical, risk_levels):
    p = a_medium_project
    ids, total = _all_pages(
        client,
        "/projects/query",
        {
            "state": p["state"],
            "district": p["district"],
            "constituency": p["constituency"],
            "risk_level": "MEDIUM",
        },
        auth_headers,
    )
    expected = _expected_ids(
        canonical, risk_levels,
        state=p["state"], district=p["district"],
        constituency=p["constituency"], risk="MEDIUM",
    )
    assert p["work_id"] in ids
    assert set(ids) == expected


# =====================================================================
# 2. Search (Project ID / description / location) on /projects/query
# =====================================================================

def test_search_by_project_id(client, auth_headers):
    body = client.get(f"/projects/query?search={_q(REAL_PROJECT_ID)}", headers=auth_headers).json()
    assert body["total"] >= 1
    assert REAL_PROJECT_ID in [item["project_id"] for item in body["items"]]


def test_search_by_location_field(client, auth_headers, canonical):
    body = client.get(f"/projects/query?search={_q(REAL_DISTRICT)}&limit=50", headers=auth_headers).json()
    assert body["total"] >= 1
    expected = int((canonical["district"].map(_fold) == _fold(REAL_DISTRICT)).sum())
    assert body["total"] >= expected  # district matches, plus any other field that mentions it
    assert all(
        REAL_DISTRICT.casefold() in " ".join(str(v) for v in item.values() if v is not None).casefold()
        for item in body["items"]
    )


def test_search_by_description_text(client, auth_headers, canonical):
    """A distinctive word from a real work description finds that project."""
    frame = canonical[canonical["work_description"].notna()]
    target = None
    for _, row in frame.head(500).iterrows():
        words = [w for w in str(row["work_description"]).split() if w.isalpha() and len(w) >= 8]
        if words:
            target = (str(row["work_id"]).strip(), words[0])
            break
    assert target, "no usable description found in the first 500 rows"
    work_id, word = target
    ids, _total = _all_pages(client, "/projects/query", {"search": word}, auth_headers)
    assert work_id in ids


# =====================================================================
# 3. RBAC: filters can only narrow, never widen
# =====================================================================

@pytest.fixture()
def state_headers(client, db_session):
    return make_scoped_headers(
        client, db_session,
        email="state.map@example.gov.in",
        role="State Nodal Officer",
        full_name="State Nodal",
        scope_state=REAL_STATE,
    )


@pytest.fixture()
def district_headers(client, db_session):
    return make_scoped_headers(
        client, db_session,
        email="district.map@example.gov.in",
        role="District Authority",
        full_name="District Auth",
        scope_state=REAL_STATE,
        scope_district=REAL_DISTRICT,
    )


def test_scoped_risk_filter_stays_inside_the_state(client, state_headers, canonical, risk_levels):
    ids, total = _all_pages(client, "/projects/query", {"risk_level": "MEDIUM"}, state_headers)
    expected = _expected_ids(canonical, risk_levels, state=REAL_STATE, risk="MEDIUM")
    assert total == len(expected) > 0
    assert set(ids) == expected


def test_scoped_risk_filter_cannot_reach_other_states(client, state_headers, canonical, risk_levels):
    """HIGH projects exist nationally, but none in this state's scope leak
    through a risk-only query."""
    national_high = _expected_ids(canonical, risk_levels, risk="HIGH")
    own_high = _expected_ids(canonical, risk_levels, state=REAL_STATE, risk="HIGH")
    body = client.get("/projects/query?risk_level=HIGH&limit=50", headers=state_headers).json()
    assert body["total"] == len(own_high)
    assert body["total"] <= len(national_high)
    assert {i["project_id"] for i in body["items"]} <= own_high


def test_naming_another_state_with_a_risk_filter_is_still_refused(client, state_headers, canonical):
    other = next(
        str(s).strip()
        for s in canonical["state"].dropna().unique()
        if _fold(s) != _fold(REAL_STATE)
    )
    resp = client.get(f"/projects/query?state={_q(other)}&risk_level=HIGH", headers=state_headers)
    assert resp.status_code == 403


def test_district_scope_cannot_filter_to_another_district(client, district_headers, canonical):
    other = next(
        str(d).strip()
        for d in canonical[canonical["state"].map(_fold) == _fold(REAL_STATE)]["district"].dropna().unique()
        if _fold(d) != _fold(REAL_DISTRICT)
    )
    resp = client.get(f"/projects/query?district={_q(other)}&risk_level=MEDIUM", headers=district_headers)
    assert resp.status_code == 403


def test_unscoped_account_gets_nothing_from_any_filter(client, db_session):
    headers = make_scoped_headers(
        client, db_session,
        email="nobody.map@example.gov.in",
        role="District Authority",
    )
    body = client.get("/projects/query?risk_level=HIGH", headers=headers).json()
    assert body["total"] == 0
    assert body["items"] == []


def test_protected_endpoints_still_require_a_token(client):
    assert client.get("/projects/query?risk_level=HIGH").status_code in (401, 403)
    assert client.get("/projects/filter-options").status_code in (401, 403)


# =====================================================================
# 4. /projects/filter-options: cascading + scope
# =====================================================================

def test_filter_options_without_params_are_unchanged(client, auth_headers, canonical):
    body = client.get("/projects/filter-options", headers=auth_headers).json()
    assert len(body["states"]) == canonical["state"].dropna().map(_fold).nunique()
    assert len(body["districts"]) == canonical["district"].dropna().map(_fold).nunique()
    assert len(body["constituencies"]) > 0
    assert body["locked_filters"] == []


def test_filter_options_districts_cascade_from_state(client, auth_headers, canonical):
    body = client.get(f"/projects/filter-options?state={_q(REAL_STATE)}", headers=auth_headers).json()
    expected = {
        str(d).strip()
        for d in canonical[canonical["state"].map(_fold) == _fold(REAL_STATE)]["district"].dropna()
    }
    assert set(body["districts"]) == expected
    assert 0 < len(body["districts"]) < 200
    # The state list itself is never narrowed.
    assert len(body["states"]) > 1


def test_filter_options_constituencies_cascade_from_state_and_district(client, auth_headers, canonical):
    body = client.get(
        f"/projects/filter-options?state={_q(REAL_STATE)}&district={_q(REAL_DISTRICT)}",
        headers=auth_headers,
    ).json()
    frame = canonical[
        (canonical["state"].map(_fold) == _fold(REAL_STATE))
        & (canonical["district"].map(_fold) == _fold(REAL_DISTRICT))
    ]
    assert set(body["constituencies"]) == {str(c).strip() for c in frame["constituency"].dropna()}


def test_filter_options_cascade_never_leaks_outside_scope(client, district_headers, canonical):
    """A district-scoped account asking about another state learns nothing."""
    other = next(
        str(s).strip()
        for s in canonical["state"].dropna().unique()
        if _fold(s) != _fold(REAL_STATE)
    )
    body = client.get(f"/projects/filter-options?state={_q(other)}", headers=district_headers).json()
    assert body["districts"] == []
    assert body["constituencies"] == []
    assert body["states"] == [REAL_STATE] or [_fold(s) for s in body["states"]] == [_fold(REAL_STATE)]


def test_filter_options_report_locked_dimensions_for_scoped_roles(client, district_headers, state_headers):
    district = client.get("/projects/filter-options", headers=district_headers).json()
    assert "state" in district["locked_filters"]
    assert "district" in district["locked_filters"]
    state = client.get("/projects/filter-options", headers=state_headers).json()
    assert state["locked_filters"] == ["state"]
    assert len(state["districts"]) > 1


# =====================================================================
# 5. Demo mode (no JWT, unscoped)
# =====================================================================

def test_demo_query_needs_no_authentication(client):
    assert client.get("/demo/projects/query?limit=1").status_code == 200
    assert client.get("/demo/projects/filter-options").status_code == 200


def test_demo_query_filters_by_district(client, canonical, risk_levels):
    ids, total = _all_pages(
        client, "/demo/projects/query",
        {"state": REAL_STATE, "district": REAL_DISTRICT},
    )
    expected = _expected_ids(canonical, risk_levels, state=REAL_STATE, district=REAL_DISTRICT)
    assert total == len(expected) > 0
    assert set(ids) == expected


def test_demo_query_filters_by_constituency(client, a_medium_project, canonical, risk_levels):
    p = a_medium_project
    ids, total = _all_pages(client, "/demo/projects/query", {"constituency": p["constituency"]})
    expected = _expected_ids(canonical, risk_levels, constituency=p["constituency"])
    assert total == len(expected) > 0
    assert set(ids) == expected


def test_demo_query_filters_by_risk_level(client, canonical, risk_levels):
    ids, total = _all_pages(client, "/demo/projects/query", {"risk_level": "HIGH"})
    expected = _expected_ids(canonical, risk_levels, risk="HIGH")
    assert total == len(expected) > 0
    assert set(ids) == expected


def test_demo_query_rejects_unknown_risk_level(client):
    assert client.get("/demo/projects/query?risk_level=SEVERE").status_code == 422


def test_demo_query_combines_all_filters(client, a_medium_project):
    p = a_medium_project
    body = client.get(
        "/demo/projects/query?limit=300"
        f"&state={_q(p['state'])}&district={_q(p['district'])}"
        f"&constituency={_q(p['constituency'])}&risk_level=MEDIUM"
        f"&search={_q(p['work_id'])}"
    ).json()
    assert [i["project_id"] for i in body["items"]] == [p["work_id"]]
    assert body["total"] == 1


def test_demo_query_search_by_id_description_and_location(client, canonical):
    by_id = client.get(f"/demo/projects/query?search={_q(REAL_PROJECT_ID)}").json()
    assert REAL_PROJECT_ID in [i["project_id"] for i in by_id["items"]]
    by_location = client.get(f"/demo/projects/query?search={_q(REAL_DISTRICT)}&limit=5").json()
    assert by_location["total"] >= 1


def test_demo_and_authenticated_query_agree(client, auth_headers, a_medium_project):
    """Same filters -> same projects, same risk overlay, on both surfaces."""
    p = a_medium_project
    params = f"state={_q(p['state'])}&district={_q(p['district'])}&risk_level=MEDIUM&limit=50"
    real = client.get(f"/projects/query?{params}", headers=auth_headers).json()
    demo = client.get(f"/demo/projects/query?{params}").json()
    assert real["total"] == demo["total"]
    assert [i["project_id"] for i in real["items"]] == [i["project_id"] for i in demo["items"]]
    assert [i["risk_level"] for i in real["items"]] == [i["risk_level"] for i in demo["items"]]
    assert [i["risk_score"] for i in real["items"]] == [i["risk_score"] for i in demo["items"]]


def test_demo_items_keep_phase2_coordinates(client):
    """Filtering must not disturb the Phase 2 coordinate fix."""
    body = client.get(
        f"/demo/projects/query?state={_q(REAL_STATE)}&district={_q(REAL_DISTRICT)}&limit=5"
    ).json()
    assert body["items"]
    for item in body["items"]:
        assert item["latitude"] is not None
        assert item["longitude"] is not None
        assert item["location_precision"] in ("district_centroid", "state_centroid")


def test_demo_filter_options_are_unscoped_and_cascade(client, canonical):
    everything = client.get("/demo/projects/filter-options").json()
    assert everything["locked_filters"] == []
    assert everything["scope"] is None
    assert len(everything["states"]) == canonical["state"].dropna().map(_fold).nunique()

    in_state = client.get(f"/demo/projects/filter-options?state={_q(REAL_STATE)}").json()
    assert 0 < len(in_state["districts"]) < len(everything["districts"])

    in_district = client.get(
        f"/demo/projects/filter-options?state={_q(REAL_STATE)}&district={_q(REAL_DISTRICT)}"
    ).json()
    assert 0 < len(in_district["constituencies"]) < len(in_state["constituencies"])


def test_demo_filter_options_route_is_not_swallowed_as_a_project_id(client):
    """/demo/projects/filter-options must resolve to the options endpoint,
    not to GET /demo/projects/{project_id:path} (which would 404)."""
    resp = client.get("/demo/projects/filter-options")
    assert resp.status_code == 200
    assert "states" in resp.json()


# =====================================================================
# 6. Public surface (defensive path)
# =====================================================================

def _seed(db_session, **overrides):
    defaults = dict(
        project_id="WS/PUBLIC/FILTER/1",
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
    db_session.add(Project(**defaults))
    db_session.commit()


def test_public_projects_filter_by_district_and_constituency(client, db_session):
    _seed(db_session)
    _seed(db_session, project_id="WS/PUBLIC/FILTER/2", district="Patna", constituency="Patna Sahib")
    _seed(db_session, project_id="WS/PUBLIC/FILTER/3", district="Gaya", constituency="Gaya")

    by_district = client.get("/public/projects?district=Samastipur").json()
    assert [i["project_id"] for i in by_district["items"]] == ["WS/PUBLIC/FILTER/1"]

    by_constituency = client.get("/public/projects?constituency=Patna%20Sahib").json()
    assert {i["project_id"] for i in by_constituency["items"]} == {
        "WS/PUBLIC/FILTER/1",
        "WS/PUBLIC/FILTER/2",
    }

    combined = client.get("/public/projects?district=Patna&constituency=Patna%20Sahib").json()
    assert [i["project_id"] for i in combined["items"]] == ["WS/PUBLIC/FILTER/2"]


def test_public_projects_search_matches_district(client, db_session):
    _seed(db_session)
    _seed(db_session, project_id="WS/PUBLIC/FILTER/3", district="Gaya", constituency="Gaya")
    body = client.get("/public/projects?search=samastipur").json()
    assert [i["project_id"] for i in body["items"]] == ["WS/PUBLIC/FILTER/1"]


def test_public_projects_never_expose_risk_fields(client, db_session):
    _seed(db_session)
    item = client.get("/public/projects?district=Samastipur").json()["items"][0]
    assert not any(key.startswith("risk") for key in item)