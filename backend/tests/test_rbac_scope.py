"""
RBAC security tests: data scoping and cross-role isolation.

These tests exercise the BACKEND directly. Every assertion here is about
what the API returns to a raw HTTP call -- none of them depend on the
frontend hiding anything, because frontend hiding is not authorization.

What is proven here
-------------------
  1. A scoped account's list endpoints return ONLY its jurisdiction.
  2. A scoped account cannot read an out-of-scope project by typing its
     ID into the URL, and cannot reach that project's risk by calling
     the risk endpoint directly.
  3. Out-of-scope and non-existent both return 404 with the same body,
     so 403-vs-404 cannot be used to enumerate real work IDs.
  4. Alerts, analytics and report exports are scope-filtered too.
  5. A client-supplied filter cannot widen scope.
  6. The same project is visible to the correct Ministry / State /
     District / MP accounts and invisible to the wrong ones -- with an
     identical Risk Fusion score for everyone who can see it.
  7. An account with no assigned jurisdiction sees nothing, rather than
     falling back to national data.
  8. Ministry/Admin behaviour is unchanged.

The scopes below are read from the REAL canonical dataset at test time
(see the `sample_project` fixture) rather than hardcoded, so these tests
follow the data instead of asserting facts about a snapshot.
"""

import urllib.parse

import pytest

from tests.conftest import make_scoped_headers


PASSWORD = "SecurePass123"


# ---------------------------------------------------------------------
# Real sample rows, taken from the canonical dataset itself
# ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def canonical():
    from app.aggregations import load_canonical_projects

    return load_canonical_projects()


@pytest.fixture(scope="module")
def sample_project(canonical):
    """One real project that has a state, a district and a genuine
    parliamentary constituency (not a Rajya Sabha sentinel).

    Everything downstream -- the "correct" MP/District/State accounts and
    the "wrong" ones -- is derived from this single real row, so the
    tests describe actual relationships in the data rather than invented
    ones.
    """
    frame = canonical[
        canonical["state"].notna()
        & canonical["district"].notna()
        & canonical["constituency"].notna()
        & ~canonical["constituency"].astype(str).str.contains("Rajya Sabha", case=False, na=False)
    ].copy()
    assert not frame.empty, "canonical dataset has no fully-located project to test with"

    # Pick from the state with the MOST distinct constituencies and
    # districts, so the "different constituency, same state" and
    # "different district, same state" fixtures below have something real
    # to point at. A small single-seat state (Sikkim, for instance) would
    # make those negative cases impossible to construct.
    frame["state"] = frame["state"].astype(str).str.strip()
    frame["district"] = frame["district"].astype(str).str.strip()
    frame["constituency"] = frame["constituency"].astype(str).str.strip()

    spread = (
        frame.groupby("state")
        .agg(constituencies=("constituency", "nunique"), districts=("district", "nunique"))
        .sort_values(["constituencies", "districts"], ascending=False)
    )
    best_state = str(spread.index[0])
    assert spread.iloc[0]["constituencies"] > 1
    assert spread.iloc[0]["districts"] > 1

    row = frame[frame["state"] == best_state].iloc[0]
    return {
        "work_id": str(row["work_id"]).strip(),
        "state": str(row["state"]).strip(),
        "district": str(row["district"]).strip(),
        "constituency": str(row["constituency"]).strip(),
    }


@pytest.fixture(scope="module")
def other_project(canonical, sample_project):
    """A real project in a DIFFERENT state from `sample_project`."""
    frame = canonical[
        canonical["state"].notna()
        & canonical["district"].notna()
        & (canonical["state"].astype(str).str.strip() != sample_project["state"])
    ]
    assert not frame.empty
    row = frame.iloc[0]
    return {
        "work_id": str(row["work_id"]).strip(),
        "state": str(row["state"]).strip(),
        "district": str(row["district"]).strip(),
    }


def _encode(work_id: str) -> str:
    """MPLADS work IDs contain '/', so they must be percent-encoded."""
    return urllib.parse.quote(work_id, safe="")


# ---------------------------------------------------------------------
# Account fixtures built from the real sample row
# ---------------------------------------------------------------------

@pytest.fixture()
def mp_headers(client, db_session, sample_project):
    return make_scoped_headers(
        client, db_session,
        email="mp.correct@example.gov.in",
        role="Member of Parliament",
        full_name="Test MP",
        scope_state=sample_project["state"],
        scope_constituency=sample_project["constituency"],
    )


@pytest.fixture()
def other_mp_headers(client, db_session, canonical, sample_project):
    """An MP for a DIFFERENT constituency in the same state."""
    frame = canonical[
        (canonical["state"].astype(str).str.strip() == sample_project["state"])
        & canonical["constituency"].notna()
        & (canonical["constituency"].astype(str).str.strip() != sample_project["constituency"])
        & ~canonical["constituency"].astype(str).str.contains("Rajya Sabha", case=False, na=False)
    ]
    assert not frame.empty
    other_constituency = str(frame.iloc[0]["constituency"]).strip()
    return make_scoped_headers(
        client, db_session,
        email="mp.other@example.gov.in",
        role="Member of Parliament",
        scope_state=sample_project["state"],
        scope_constituency=other_constituency,
    )


@pytest.fixture()
def district_headers(client, db_session, sample_project):
    return make_scoped_headers(
        client, db_session,
        email="district.correct@example.gov.in",
        role="District Authority",
        scope_state=sample_project["state"],
        scope_district=sample_project["district"],
    )


@pytest.fixture()
def other_district_headers(client, db_session, canonical, sample_project):
    """A District Authority for a DIFFERENT district in the SAME state.

    Same-state rather than another state on purpose: it is the harder
    case. If scoping were sloppily implemented as a state check, this
    account would wrongly pass, and the isolation tests below would not
    catch it.
    """
    frame = canonical[
        (canonical["state"].astype(str).str.strip() == sample_project["state"])
        & canonical["district"].notna()
        & (canonical["district"].astype(str).str.strip() != sample_project["district"])
    ]
    assert not frame.empty
    other_district = str(frame.iloc[0]["district"]).strip()
    return make_scoped_headers(
        client, db_session,
        email="district.other@example.gov.in",
        role="District Authority",
        scope_state=sample_project["state"],
        scope_district=other_district,
    )


@pytest.fixture()
def state_headers(client, db_session, sample_project):
    return make_scoped_headers(
        client, db_session,
        email="state.correct@example.gov.in",
        role="State Nodal Officer",
        scope_state=sample_project["state"],
    )


@pytest.fixture()
def other_state_headers(client, db_session, other_project):
    return make_scoped_headers(
        client, db_session,
        email="state.other@example.gov.in",
        role="State Nodal Officer",
        scope_state=other_project["state"],
    )


@pytest.fixture()
def unscoped_headers(client, db_session):
    """A jurisdictional role with NO assignment -- the provisioning gap."""
    return make_scoped_headers(
        client, db_session,
        email="unassigned@example.gov.in",
        role="District Authority",
    )


# =====================================================================
# 1. Role resolution (unit level)
# =====================================================================

def test_unknown_role_title_does_not_fall_back_to_national():
    """The escalation this closes: an invented role title must not be
    treated as Ministry. It resolves to UNSCOPED, which authorizes
    nothing."""
    from app.rbac import ROLE_MINISTRY, ROLE_UNSCOPED, normalize_role

    assert normalize_role("Chief Data Wizard") == ROLE_UNSCOPED
    assert normalize_role("Chief Data Wizard") != ROLE_MINISTRY
    assert normalize_role(None) == ROLE_UNSCOPED
    assert normalize_role("") == ROLE_UNSCOPED


def test_existing_ministry_titles_still_resolve_to_national():
    """Regression: no currently-privileged account loses privilege."""
    from app.rbac import ROLE_MINISTRY, normalize_role

    for title in ("Administrator", "admin", "Ministry", "Ministry of Rural Development"):
        assert normalize_role(title) == ROLE_MINISTRY


def test_jurisdictional_titles_resolve_to_their_roles():
    from app.rbac import (
        ROLE_DISTRICT_AUTHORITY,
        ROLE_MP,
        ROLE_STATE_NODAL,
        normalize_role,
    )

    assert normalize_role("State Nodal Officer") == ROLE_STATE_NODAL
    assert normalize_role("District Authority") == ROLE_DISTRICT_AUTHORITY
    assert normalize_role("Member of Parliament") == ROLE_MP
    assert normalize_role("MP") == ROLE_MP


def test_role_with_no_assigned_jurisdiction_resolves_to_empty_scope():
    from app.models import User
    from app.rbac import resolve_user_scope

    user = User(id=1, email="x@y.gov.in", password_hash="x", role="District Authority", is_active=True)
    scope = resolve_user_scope(user)
    assert scope.is_empty
    assert not scope.is_national


# =====================================================================
# 2. List endpoints are scoped
# =====================================================================

def test_mp_project_list_contains_only_their_constituency(client, mp_headers, sample_project):
    resp = client.get("/projects/query?limit=100", headers=mp_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"], "the MP's own constituency should have projects"
    for item in body["items"]:
        assert item["constituency"] == sample_project["constituency"]
        assert item["state"] == sample_project["state"]


def test_district_project_list_contains_only_their_district(client, district_headers, sample_project):
    resp = client.get("/projects/query?limit=100", headers=district_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["district"] == sample_project["district"]


def test_state_project_list_contains_only_their_state(client, state_headers, sample_project):
    resp = client.get("/projects/query?limit=100", headers=state_headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["state"] == sample_project["state"]


def test_scoped_total_is_smaller_than_national_total(client, state_headers, auth_headers):
    """The scoped `total` must be the count WITHIN scope, not the
    national count with rows hidden at render time."""
    scoped = client.get("/projects/query?limit=1", headers=state_headers).json()
    national = client.get("/projects/query?limit=1", headers=auth_headers).json()
    assert scoped["total"] < national["total"]
    assert national["total"] > 0


def test_unscoped_account_sees_no_projects_not_national_data(client, unscoped_headers):
    resp = client.get("/projects/query?limit=50", headers=unscoped_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []
    assert body["empty_state_message"]


def test_plain_project_list_is_scoped_too(client, state_headers, sample_project):
    """GET /projects (the non-filtered listing) is scoped as well -- it is
    not an unguarded alternative to /projects/query."""
    resp = client.get("/projects?limit=100", headers=state_headers)
    assert resp.status_code == 200
    for item in resp.json():
        assert item["state"] == sample_project["state"]


# =====================================================================
# 3. Direct project access is blocked
# =====================================================================

def test_mp_cannot_read_a_project_from_another_constituency(client, other_mp_headers, sample_project):
    resp = client.get(f"/projects/{_encode(sample_project['work_id'])}", headers=other_mp_headers)
    assert resp.status_code == 404


def test_district_cannot_read_a_project_from_another_district(client, other_district_headers, sample_project):
    resp = client.get(f"/projects/{_encode(sample_project['work_id'])}", headers=other_district_headers)
    assert resp.status_code == 404


def test_state_cannot_read_a_project_from_another_state(client, other_state_headers, sample_project):
    resp = client.get(f"/projects/{_encode(sample_project['work_id'])}", headers=other_state_headers)
    assert resp.status_code == 404


def test_out_of_scope_and_nonexistent_are_indistinguishable(client, other_state_headers, sample_project):
    """403-vs-404 must not be usable as an existence oracle."""
    out_of_scope = client.get(f"/projects/{_encode(sample_project['work_id'])}", headers=other_state_headers)
    nonexistent = client.get("/projects/WS%2FDOES%2FNOT%2FEXIST", headers=other_state_headers)

    assert out_of_scope.status_code == nonexistent.status_code == 404
    assert out_of_scope.json()["detail"] == nonexistent.json()["detail"]


def test_out_of_scope_project_leaks_no_financial_or_risk_fields(client, other_state_headers, sample_project):
    resp = client.get(f"/projects/{_encode(sample_project['work_id'])}", headers=other_state_headers)
    body = resp.text.lower()
    for leaked in ("sanctioned_amount", "expenditure", "risk_score", "risk_level"):
        assert leaked not in body


# =====================================================================
# 4. The risk endpoint is not a side door
# =====================================================================

def test_risk_endpoint_enforces_project_scope_independently(client, other_state_headers, sample_project):
    """Skipping /projects/{id} and calling /risk directly must not work."""
    resp = client.get(f"/projects/{_encode(sample_project['work_id'])}/risk", headers=other_state_headers)
    assert resp.status_code == 404


def test_authorized_roles_all_receive_the_identical_risk_score(
    client, auth_headers, state_headers, district_headers, mp_headers, sample_project
):
    """The single most important non-leak assertion in this file: access
    differs by role, the risk calculation does not."""
    path = f"/projects/{_encode(sample_project['work_id'])}/risk"

    scores = []
    for headers in (auth_headers, state_headers, district_headers, mp_headers):
        resp = client.get(path, headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        scores.append((body["risk_score"], body["risk_level"]))

    assert len(set(scores)) == 1, f"risk differed between roles: {scores}"


def test_same_project_visible_to_correct_roles_and_invisible_to_wrong_ones(
    client,
    auth_headers,
    state_headers,
    district_headers,
    mp_headers,
    other_state_headers,
    other_district_headers,
    other_mp_headers,
    sample_project,
):
    """The cross-role acceptance test: one real project, seven accounts."""
    path = f"/projects/{_encode(sample_project['work_id'])}"

    for name, headers in (
        ("ministry", auth_headers),
        ("correct state", state_headers),
        ("correct district", district_headers),
        ("correct mp", mp_headers),
    ):
        assert client.get(path, headers=headers).status_code == 200, f"{name} should see it"

    for name, headers in (
        ("unrelated state", other_state_headers),
        ("unrelated district", other_district_headers),
        ("unrelated mp", other_mp_headers),
    ):
        assert client.get(path, headers=headers).status_code == 404, f"{name} must not see it"


# =====================================================================
# 5. Client filters cannot widen scope
# =====================================================================

def test_filter_naming_another_state_is_refused(client, state_headers, other_project):
    resp = client.get(
        f"/projects/query?state={urllib.parse.quote(other_project['state'])}",
        headers=state_headers,
    )
    assert resp.status_code == 403


def test_filter_naming_own_state_is_allowed(client, state_headers, sample_project):
    resp = client.get(
        f"/projects/query?state={urllib.parse.quote(sample_project['state'])}",
        headers=state_headers,
    )
    assert resp.status_code == 200


def test_district_cannot_filter_to_another_district(client, district_headers, other_project):
    resp = client.get(
        f"/projects/query?district={urllib.parse.quote(other_project['district'])}",
        headers=district_headers,
    )
    assert resp.status_code == 403


def test_search_cannot_reach_outside_scope(client, other_state_headers, sample_project):
    """Free-text search runs on the already-scoped frame, so searching for
    an out-of-scope work ID finds nothing."""
    resp = client.get(
        f"/projects/query?search={urllib.parse.quote(sample_project['work_id'])}",
        headers=other_state_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_filter_options_are_restricted_to_scope(client, district_headers, sample_project):
    """A District Authority is never offered an 'All States' dropdown."""
    resp = client.get("/projects/filter-options", headers=district_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["states"] == [sample_project["state"]]
    assert body["districts"] == [sample_project["district"]]
    assert "state" in body["locked_filters"]
    assert "district" in body["locked_filters"]


# =====================================================================
# 6. Alerts are scoped
# =====================================================================

def test_alerts_list_is_scoped_to_the_state(client, state_headers, sample_project):
    resp = client.get("/alerts?limit=100", headers=state_headers)
    assert resp.status_code == 200
    for alert in resp.json():
        if alert.get("state"):
            assert alert["state"] == sample_project["state"]


def test_alerts_for_unscoped_account_are_empty(client, unscoped_headers):
    resp = client.get("/alerts?limit=50", headers=unscoped_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_alert_detail_is_blocked_for_out_of_scope_project(client, other_state_headers, sample_project):
    resp = client.get(f"/alerts/{_encode(sample_project['work_id'])}", headers=other_state_headers)
    assert resp.status_code == 404


def test_alert_pagination_cannot_walk_into_other_jurisdictions(client, district_headers, sample_project):
    """Scoping happens before pagination, so no page exposes another
    district's alerts."""
    for skip in (0, 50, 100):
        resp = client.get(f"/alerts?skip={skip}&limit=50", headers=district_headers)
        assert resp.status_code == 200
        for alert in resp.json():
            if alert.get("district"):
                assert alert["district"] == sample_project["district"]


# =====================================================================
# 7. Analytics are scoped
# =====================================================================

def test_analytics_totals_are_scoped_not_national(client, state_headers, auth_headers):
    scoped = client.get("/analytics", headers=state_headers)
    national = client.get("/analytics", headers=auth_headers)
    assert scoped.status_code == national.status_code == 200
    assert scoped.json()["total_projects"] < national.json()["total_projects"]


def test_analytics_by_state_for_a_state_user_lists_only_their_state(client, state_headers, sample_project):
    body = client.get("/analytics", headers=state_headers).json()
    states = [entry["state"] for entry in body["by_state"]]
    assert states == [sample_project["state"]]


def test_analytics_reports_the_scope_it_used(client, district_headers, sample_project):
    body = client.get("/analytics", headers=district_headers).json()
    assert body["scope"]["type"] == "district"
    assert body["scope"]["district"] == sample_project["district"]


def test_analytics_for_unscoped_account_is_zero(client, unscoped_headers):
    body = client.get("/analytics", headers=unscoped_headers).json()
    assert body["total_projects"] == 0


# =====================================================================
# 8. Reports and exports are scoped
# =====================================================================

def test_reports_meta_is_available_to_a_scoped_role(client, state_headers, sample_project):
    """Reporting is no longer Ministry-only -- but it is scoped."""
    body = client.get("/reports/meta", headers=state_headers).json()
    assert body["scope_available"] is True
    assert sample_project["state"] in body["scope_label"]


def test_reports_meta_does_not_offer_a_locked_filter(client, district_headers):
    body = client.get("/reports/meta", headers=district_headers).json()
    assert "state" not in body["filters_supported"]
    assert "district" not in body["filters_supported"]


def test_report_scope_label_never_claims_national_for_a_scoped_role(client, state_headers, sample_project):
    body = client.get(
        "/reports/generate?report_type=project_monitoring&format=json",
        headers=state_headers,
    ).json()
    assert body["scope"] != "National"
    assert sample_project["state"] in body["scope"]


def test_report_generation_refuses_another_jurisdiction(client, state_headers, other_project):
    resp = client.get(
        "/reports/generate?report_type=project_monitoring&format=json"
        f"&state={urllib.parse.quote(other_project['state'])}",
        headers=state_headers,
    )
    assert resp.status_code == 403


def test_csv_export_contains_no_out_of_scope_rows(client, district_headers, sample_project, other_project):
    resp = client.get(
        "/reports/generate?report_type=project_monitoring&format=csv",
        headers=district_headers,
    )
    assert resp.status_code == 200
    content = resp.text
    assert other_project["work_id"] not in content


def test_single_project_pdf_export_respects_project_scope(client, other_state_headers, sample_project):
    """The per-project PDF is not a way around project authorization."""
    resp = client.get(
        f"/reports/project/{_encode(sample_project['work_id'])}?format=json",
        headers=other_state_headers,
    )
    assert resp.status_code == 404


# =====================================================================
# 9. Dashboards are scoped
# =====================================================================

def test_role_overview_gives_each_role_its_own_dashboard_key(
    client, auth_headers, state_headers, district_headers, mp_headers
):
    expected = {
        "ministry": auth_headers,
        "state": state_headers,
        "district": district_headers,
        "mp": mp_headers,
    }
    for dashboard, headers in expected.items():
        body = client.get("/dashboard/role-overview", headers=headers).json()
        assert body["scope_available"] is True, body.get("unavailable_reason")
        assert body["dashboard"] == dashboard


def test_mp_dashboard_kpis_are_constituency_scoped(client, mp_headers, auth_headers):
    mp_body = client.get("/dashboard/role-overview", headers=mp_headers).json()
    national = client.get("/dashboard/stats", headers=auth_headers).json()
    assert mp_body["kpis"]["total_projects"] > 0
    assert mp_body["kpis"]["total_projects"] < national["total_projects"]


def test_state_dashboard_includes_district_comparison(client, state_headers):
    body = client.get("/dashboard/role-overview", headers=state_headers).json()
    assert body["district_performance"], "State Nodal dashboard needs district rows"


def test_district_dashboard_has_no_cross_district_comparison(client, district_headers):
    """A District Authority has no business comparing other districts."""
    body = client.get("/dashboard/role-overview", headers=district_headers).json()
    assert body["district_performance"] == []


def test_dashboard_stats_is_scoped(client, state_headers, auth_headers):
    scoped = client.get("/dashboard/stats", headers=state_headers).json()
    national = client.get("/dashboard/stats", headers=auth_headers).json()
    assert scoped["total_projects"] < national["total_projects"]


def test_unscoped_dashboard_reports_unavailable_not_national(client, unscoped_headers):
    body = client.get("/dashboard/role-overview", headers=unscoped_headers).json()
    assert body["scope_available"] is False
    assert body["unavailable_reason"]
    assert body["kpis"] is None


def test_every_dashboard_states_its_scope(client, state_headers, district_headers, mp_headers):
    """The trust requirement: a dashboard must say what it is showing."""
    for headers in (state_headers, district_headers, mp_headers):
        body = client.get("/dashboard/role-overview", headers=headers).json()
        assert body["scope_indicator"]
        assert "Showing" in body["scope_indicator"]


# =====================================================================
# 10. Permissions and identity
# =====================================================================

def test_auth_me_exposes_the_resolved_role_and_scope(client, mp_headers, sample_project):
    body = client.get("/auth/me", headers=mp_headers).json()
    assert body["role_key"] == "MP"
    assert body["scope"]["constituency"] == sample_project["constituency"]
    assert body["scope"]["type"] == "constituency"
    assert "password_hash" not in body


def test_mp_does_not_hold_administrative_permissions(client, mp_headers):
    body = client.get("/auth/me", headers=mp_headers).json()
    for administrative in ("UPLOAD_DATA", "MANAGE_USERS", "VIEW_REVIEW_QUEUE"):
        assert administrative not in body["permissions"]


def test_district_authority_holds_the_review_queue_permission(client, district_headers):
    body = client.get("/auth/me", headers=district_headers).json()
    assert "VIEW_REVIEW_QUEUE" in body["permissions"]


def test_unscoped_account_is_authorized_for_no_data(client, unscoped_headers):
    """A recognised role title with no jurisdiction assigned still holds
    its role's capabilities -- but they resolve to zero records, which is
    what actually matters. Capability and data scope are separate axes on
    purpose: an officer awaiting provisioning sees their own cockpit with
    honest empty states, not somebody else's projects."""
    body = client.get("/auth/me", headers=unscoped_headers).json()
    assert body["scope_available"] is False
    assert body["scope"]["type"] == "none"
    assert body["empty_state_message"]
    assert client.get("/projects/query", headers=unscoped_headers).json()["total"] == 0


def test_unrecognised_role_title_holds_no_permissions_at_all(client, db_session):
    """An invented role title is not a capability grant."""
    headers = make_scoped_headers(
        client, db_session,
        email="mystery.title@example.gov.in",
        role="Chief Data Wizard",
        scope_state="Maharashtra",
    )
    body = client.get("/auth/me", headers=headers).json()
    assert body["role_key"] == "UNSCOPED"
    assert body["permissions"] == []
    assert body["scope_available"] is False


def test_upload_remains_ministry_only(client, state_headers, district_headers, mp_headers):
    """Regression: the existing Ministry-only upload gate still holds for
    every newly-wired role."""
    for headers in (state_headers, district_headers, mp_headers):
        resp = client.post("/upload-analyze", headers=headers, files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")})
        assert resp.status_code == 403


# =====================================================================
# 11. Ministry regression
# =====================================================================

def test_ministry_still_sees_the_full_universe(client, auth_headers):
    body = client.get("/dashboard/stats", headers=auth_headers).json()
    assert body["total_projects"] == 43863


def test_ministry_role_overview_contract_is_unchanged(client, auth_headers):
    body = client.get("/dashboard/role-overview", headers=auth_headers).json()
    assert body["scope_available"] is True
    assert body["scope_label"] == "National"
    assert body["stats"] is not None
    assert body["by_state_risk"]
    # `priority_projects` is sourced from the `projects` DB table, which
    # is empty in the SQLite test database. Its presence in the response
    # is the contract under test here, not its length -- asserting a
    # non-empty list would be asserting a fixture, not behaviour.
    assert isinstance(body["priority_projects"], list)


def test_unauthenticated_requests_are_still_401_not_403(client):
    for path in ("/projects", "/alerts", "/analytics", "/dashboard/stats", "/reports/meta"):
        assert client.get(path).status_code == 401