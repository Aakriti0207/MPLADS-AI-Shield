"""
Phase 5: tests for the public dashboard contract.

Two things are asserted here:

1.  The anonymous surface carries NO risk / AI-investigation data. This
    is checked by walking the entire JSON response recursively rather
    than by spot-checking a few keys, so a field added anywhere in a
    nested structure still trips the test.

2.  The public figures are real and internally consistent -- state and
    district aggregates reconcile with the KPI totals, and the project
    ids are the canonical `work_id`s.

`/public/insights` reads `data/processed/canonical_projects.csv`
directly and needs no database session, so these tests exercise it
without seeding anything.
"""

import pandas as pd
import pytest

from app.aggregations import CANONICAL_PROJECTS_PATH


# Substrings that must never appear in a key ANYWHERE in a public
# payload. Deliberately broad: "score" alone would catch any future
# `*_score` field, not just the ones that exist today.
FORBIDDEN_KEY_TOKENS = (
    "risk",
    "anomaly",
    "duplicate",
    "isolation",
    "fusion",
    "alert",
    "investigat",
    "review",
    "internal",
    "admin",
    "reviewer",
    "score",
    "why_risky",
    "reason",
    "evidence",
    "flag",
)

FORBIDDEN_VALUE_TOKENS = ("CRITICAL", "Risk Fusion", "isolation_forest")


def _walk_keys(payload, path="$"):
    """Yield (json_path, key) for every key in a nested JSON structure."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield f"{path}.{key}", key
            yield from _walk_keys(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            yield from _walk_keys(value, f"{path}[{index}]")


def _assert_no_sensitive_fields(payload):
    offenders = [
        (json_path, key)
        for json_path, key in _walk_keys(payload)
        for token in FORBIDDEN_KEY_TOKENS
        if token in key.lower()
    ]

    assert not offenders, f"Sensitive field(s) exposed publicly: {offenders}"


@pytest.fixture(scope="module")
def canonical_ids():
    if not CANONICAL_PROJECTS_PATH.exists():
        pytest.skip("canonical_projects.csv is not present in this checkout")

    frame = pd.read_csv(CANONICAL_PROJECTS_PATH, low_memory=False)

    return set(frame["work_id"].astype(str).str.strip())


# ---------------------------------------------------------------------------
# GET /public/overview -- the "Requiring Review" regression
# ---------------------------------------------------------------------------

def test_public_overview_no_longer_returns_risk_level_counts(client):
    resp = client.get("/public/overview")

    assert resp.status_code == 200
    assert "risk_level_counts" not in resp.json()


def test_public_overview_exposes_no_risk_or_investigation_field(client):
    resp = client.get("/public/overview")

    assert resp.status_code == 200
    _assert_no_sensitive_fields(resp.json())


def test_public_overview_still_returns_its_public_aggregates(client):
    """The risk removal must not have stripped the legitimate fields."""
    body = client.get("/public/overview").json()

    for field in (
        "total_projects",
        "total_sanctioned_amount",
        "total_expenditure",
        "by_state",
        "by_work_type",
        "status_distribution",
        "recent_projects",
    ):
        assert field in body, f"missing public field {field}"


# ---------------------------------------------------------------------------
# GET /public/overview vs GET /public/insights -- one canonical public
# data source (verification-pass fix)
#
# Before this fix, /public/overview's aggregates came from the legacy
# `Project` DB table while /public/insights came from
# canonical_projects.csv -- two different project universes that could
# legitimately disagree. These tests pin the two endpoints to report
# IDENTICAL national figures now that both compute from the same
# canonical frame.
# ---------------------------------------------------------------------------

def test_overview_and_insights_report_the_same_national_totals(client):
    overview = client.get("/public/overview").json()
    insights = client.get("/public/insights").json()

    assert overview["total_projects"] == insights["kpis"]["total_projects"]
    assert overview["total_sanctioned_amount"] == insights["kpis"]["total_sanctioned_amount"]
    assert overview["total_expenditure"] == insights["kpis"]["total_expenditure"]
    assert overview["completed_projects"] == insights["kpis"]["completed_projects"]
    assert overview["active_projects"] == insights["kpis"]["active_works"]


def test_overview_by_state_matches_insights_by_state(client):
    overview_states = {
        row["state"]: (row["total_sanctioned_amount"], row["total_expenditure"])
        for row in client.get("/public/overview").json()["by_state"]
    }
    insights_states = {
        row["state"]: (row["total_sanctioned_amount"], row["total_expenditure"])
        for row in client.get("/public/insights").json()["by_state"]
    }

    assert overview_states == insights_states


def test_overview_status_distribution_matches_insights(client):
    overview = client.get("/public/overview").json()["status_distribution"]
    insights = client.get("/public/insights").json()["status_distribution"]

    assert overview == insights


def test_overview_delayed_projects_is_null_not_fabricated_zero(client):
    """The canonical dataset has no expected-completion date, so this
    must be reported as unmeasurable (null), never as a false zero."""
    body = client.get("/public/overview").json()

    assert body["delayed_projects"] is None


def test_overview_completed_active_and_totals_partition_correctly(client):
    body = client.get("/public/overview").json()

    # completed + active no longer silently absorbs "no recorded status"
    # projects into "active" -- there must be at least as many total
    # projects as completed + active (the remainder is the unspecified
    # bucket, which /public/overview's schema has no dedicated field for
    # but which /public/insights reports explicitly).
    assert body["completed_projects"] + body["active_projects"] <= body["total_projects"]


# ---------------------------------------------------------------------------
# GET /public/insights
# ---------------------------------------------------------------------------

def test_public_insights_works_without_authentication(client):
    resp = client.get("/public/insights")

    assert resp.status_code == 200, resp.text


def test_public_insights_exposes_no_risk_or_investigation_field(client):
    body = client.get("/public/insights").json()

    _assert_no_sensitive_fields(body)

    text = client.get("/public/insights").text

    for token in FORBIDDEN_VALUE_TOKENS:
        assert token not in text, f"'{token}' leaked into the public payload"


def test_public_insights_returns_the_required_public_kpis(client):
    kpis = client.get("/public/insights").json()["kpis"]

    assert kpis["total_projects"] > 0
    assert float(kpis["total_sanctioned_amount"]) > 0
    assert float(kpis["total_expenditure"]) > 0
    assert kpis["completed_projects"] >= 0
    assert kpis["active_works"] >= 0
    assert kpis["states_covered"] > 0
    assert kpis["districts_covered"] > 0

    # Completed / active / unknown-status must partition the portfolio --
    # no project may be double counted or silently dropped.
    assert (
        kpis["completed_projects"]
        + kpis["active_works"]
        + kpis["status_not_specified"]
        == kpis["total_projects"]
    )


def test_public_trends_are_built_from_real_dates_only(client):
    trends = client.get("/public/insights").json()["trends"]

    for name in ("expenditure", "completion", "sanction"):
        trend = trends[name]

        assert trend["basis"], f"{name} trend must declare its basis"
        assert trend["points"], f"{name} trend should have real points"

        # Coverage is reported honestly, never claimed as 100% when the
        # underlying dates are sparse.
        assert trend["projects_with_data"] <= trend["total_projects"]

        months = [point["period"] for point in trend["points"]]
        assert months == sorted(months), "trend months must be chronological"
        assert len(months) == len(set(months)), "duplicate month in trend"

        # A month with no source rows must be flagged, not passed off as
        # a measured zero.
        for point in trend["points"]:
            if not point["has_records"]:
                assert point["project_count"] == 0


def test_expenditure_and_completion_trends_report_partial_coverage(client):
    """The source data is sparse; the API must say so rather than imply
    the trends cover the whole portfolio."""
    body = client.get("/public/insights").json()

    expenditure = body["trends"]["expenditure"]
    completion = body["trends"]["completion"]

    assert expenditure["projects_with_data"] < expenditure["total_projects"]
    assert completion["projects_with_data"] < completion["total_projects"]

    notes = " ".join(body["data_coverage"]["notes"]).lower()
    assert "expenditure" in notes
    assert "completion" in notes


def test_state_aggregates_reconcile_with_the_kpi_totals(client):
    body = client.get("/public/insights").json()

    kpis = body["kpis"]
    states = body["by_state"]

    assert states

    assert sum(row["project_count"] for row in states) == kpis["total_projects"]

    assert sum(
        float(row["total_expenditure"]) for row in states
    ) == pytest.approx(float(kpis["total_expenditure"]), rel=1e-6)


def test_district_aggregates_reconcile_with_their_state(client):
    body = client.get("/public/insights").json()

    top_state = body["by_state"][0]

    resp = client.get(
        "/public/insights/districts",
        params={"state": top_state["state"]},
    )

    assert resp.status_code == 200

    districts = resp.json()["districts"]

    assert districts
    assert all(row["state"] == top_state["state"] for row in districts)
    assert (
        sum(row["project_count"] for row in districts)
        == top_state["project_count"]
    )


def test_national_insights_omit_the_full_district_list(client):
    """The national payload stays light; districts come from the
    dedicated endpoint or from a state-scoped request."""
    assert client.get("/public/insights").json()["by_district"] == []

    national_districts = client.get("/public/insights/districts")

    assert national_districts.status_code == 200
    assert national_districts.json()["districts"]


def test_state_scoped_insights_narrow_every_figure(client):
    national = client.get("/public/insights").json()
    top_state = national["by_state"][0]["state"]

    scoped = client.get("/public/insights", params={"state": top_state}).json()

    assert scoped["kpis"]["total_projects"] < national["kpis"]["total_projects"]
    assert [row["state"] for row in scoped["by_state"]] == [top_state]
    assert all(row["state"] == top_state for row in scoped["by_district"])

    _assert_no_sensitive_fields(scoped)


def test_state_filter_is_case_insensitive(client):
    top_state = client.get("/public/insights").json()["by_state"][0]["state"]

    lower = client.get("/public/insights", params={"state": top_state.lower()})

    assert lower.status_code == 200
    assert lower.json()["kpis"]["total_projects"] > 0


def test_unknown_state_returns_404_rather_than_empty_zeros(client):
    resp = client.get(
        "/public/insights",
        params={"state": "Republic of Nowhere"},
    )

    assert resp.status_code == 404


def test_district_filter_requires_a_state(client):
    resp = client.get("/public/insights", params={"district": "PATNA"})

    assert resp.status_code == 400


def test_public_projects_use_the_canonical_project_id(client, canonical_ids):
    body = client.get("/public/insights").json()

    projects = body["recent_projects"]

    assert projects

    for project in projects:
        assert project["project_id"] in canonical_ids


def test_public_project_fields_match_the_public_project_contract(client):
    """Public project rows must expose only PublicProjectOut-safe fields."""
    expected = {
        "project_id",
        "state",
        "district",
        "constituency",
        "mp_name",
        "work_type",
        "implementing_agency",
        "sanctioned_amount",
        "expenditure",
        "financial_progress",
        "status",
        "sanction_date",
        "start_date",
        "expected_completion",
        "actual_completion",
        # Phase 2 Map fix: district/state-centroid fallback coordinates
        # (see app/geo_centroids.py) -- added to PublicProjectOut so
        # this surface matches the protected/demo/public-detail APIs.
        "latitude",
        "longitude",
        "location_precision",
    }

    for project in client.get("/public/insights").json()["recent_projects"]:
        assert set(project.keys()) == expected


def test_district_endpoint_is_anonymous_and_reports_unknown_states(client):
    assert client.get("/public/insights/districts").status_code == 200

    missing = client.get(
        "/public/insights/districts",
        params={"state": "Republic of Nowhere"},
    )

    assert missing.status_code == 404


def test_data_coverage_reports_missing_source_data(client):
    coverage = client.get("/public/insights").json()["data_coverage"]

    fields = {row["field"]: row for row in coverage["fields"]}

    for field in (
        "sanction_date",
        "completion_date",
        "last_expenditure_date",
        "sanction_amount",
        "total_expenditure",
    ):
        assert field in fields
        assert fields[field]["projects_with_data"] <= fields[field]["total_projects"]

    assert coverage["notes"]