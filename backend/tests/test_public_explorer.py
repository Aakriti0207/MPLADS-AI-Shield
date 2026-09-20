"""Tests for the anonymous public-portal explorer (/public/explorer/*, /public/meta).

Runs against the real canonical dataset (same approach as the existing
public/project tests). The important guarantees:

* everything works with NO Authorization header
* project ids are canonical work_ids and round-trip list -> detail
* search / filters / pagination are server-side
* responses contain ONLY allowlisted public fields -- no risk / AI /
  review data can appear, structurally or by accident
* internal routes are still protected
"""

from urllib.parse import quote

import pytest

REAL_PROJECT_ID = "WS/MP1/2023-2024/103702"

SUMMARY_FIELDS = {
    "project_id", "title", "state", "district", "constituency", "category",
    "status", "sanctioned_amount", "expenditure", "utilisation_percent",
    "sanction_date", "completion_date",
}
DETAIL_EXTRA_FIELDS = {
    "description", "mp_name", "implementing_agency", "recommended_amount",
    "recommended_date", "first_expenditure_date", "last_expenditure_date",
}

FORBIDDEN_FRAGMENTS = (
    "risk", "anomal", "score", "isolation", "duplicate", "alert",
    "review", "investig", "flag", "reason", "fusion", "compliance",
    "weight", "internal", "admin", "confidence", "explanation",
)


def _all_keys(payload):
    keys = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.add(str(key).lower())
            keys |= _all_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            keys |= _all_keys(item)
    return keys


def _assert_no_internal_keys(payload):
    for key in _all_keys(payload):
        for fragment in FORBIDDEN_FRAGMENTS:
            assert fragment not in key, f"internal-looking key '{key}' in public payload"


# --------------------------------------------------------------------- list

def test_list_is_anonymous_and_paginated(client):
    resp = client.get("/public/explorer/projects", params={"page_size": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 5
    assert body["total"] > 5
    assert body["page"] == 1 and body["page_size"] == 5
    assert body["total_pages"] * 5 >= body["total"] > (body["total_pages"] - 1) * 5

    page_two = client.get(
        "/public/explorer/projects", params={"page_size": 5, "page": 2}
    ).json()
    ids_one = {p["project_id"] for p in body["items"]}
    ids_two = {p["project_id"] for p in page_two["items"]}
    assert ids_one.isdisjoint(ids_two)


def test_list_items_expose_only_summary_fields(client):
    body = client.get("/public/explorer/projects", params={"page_size": 10}).json()
    for item in body["items"]:
        assert set(item.keys()) == SUMMARY_FIELDS
    _assert_no_internal_keys(body)


def test_search_by_canonical_project_id(client):
    body = client.get(
        "/public/explorer/projects", params={"search": REAL_PROJECT_ID}
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["project_id"] == REAL_PROJECT_ID


def test_search_by_description_words_is_case_insensitive(client):
    upper = client.get("/public/explorer/projects", params={"search": "COMMUNITY HALL"}).json()
    lower = client.get("/public/explorer/projects", params={"search": "community hall"}).json()
    assert upper["total"] == lower["total"] > 0
    titles = [(i["title"] or "").lower() for i in lower["items"]]
    assert any("community" in t and "hall" in t for t in titles)


def test_search_with_no_match_returns_empty_page_not_error(client):
    resp = client.get("/public/explorer/projects", params={"search": "zzzznotaproject"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0 and body["items"] == [] and body["total_pages"] == 0


def test_filters_narrow_results(client):
    filters = client.get("/public/explorer/filters").json()
    category = filters["categories"][0]["value"]

    everything = client.get("/public/explorer/projects", params={"page_size": 1}).json()["total"]

    by_state = client.get(
        "/public/explorer/projects", params={"state": "Maharashtra", "page_size": 20}
    ).json()
    assert 0 < by_state["total"] < everything
    assert all(i["state"] == "Maharashtra" for i in by_state["items"])

    by_status = client.get(
        "/public/explorer/projects",
        params={"state": "Maharashtra", "status": "Completed", "page_size": 20},
    ).json()
    assert 0 < by_status["total"] <= by_state["total"]
    assert all(i["status"] == "Completed" for i in by_status["items"])

    by_category = client.get(
        "/public/explorer/projects",
        params={"category": category, "page_size": 20},
    ).json()
    assert by_category["total"] > 0
    assert all(i["category"] == category for i in by_category["items"])


def test_district_filter_requires_state(client):
    assert client.get("/public/explorer/projects", params={"district": "PATNA"}).status_code == 400
    assert client.get("/public/explorer/summary", params={"district": "PATNA"}).status_code == 400


def test_district_drilldown_matches_district_options(client):
    districts = client.get("/public/explorer/filters", params={"state": "Bihar"}).json()["districts"]
    assert districts
    first = districts[0]
    body = client.get(
        "/public/explorer/projects",
        params={"state": "Bihar", "district": first["value"], "page_size": 1},
    ).json()
    assert body["total"] == first["count"]


def test_year_filter_uses_real_sanction_years(client):
    years = client.get("/public/explorer/filters").json()["years"]
    assert years and all(y["value"].isdigit() for y in years)
    pick = years[0]
    body = client.get(
        "/public/explorer/projects", params={"year": pick["value"], "page_size": 10}
    ).json()
    assert body["total"] == pick["count"]
    assert all(i["sanction_date"].startswith(pick["value"]) for i in body["items"])
    assert client.get("/public/explorer/projects", params={"year": 1800}).status_code == 422


def test_detailed_only_returns_documented_projects(client):
    body = client.get(
        "/public/explorer/projects", params={"detailed": "true", "page_size": 50}
    ).json()
    assert body["total"] > 0
    for item in body["items"]:
        assert item["title"]
        assert item["sanctioned_amount"] and item["sanctioned_amount"] > 0
    everything = client.get("/public/explorer/projects", params={"page_size": 1}).json()["total"]
    assert body["total"] < everything


def test_sort_and_size_validation(client):
    assert client.get("/public/explorer/projects", params={"sort": "risk_desc"}).status_code == 422
    assert client.get("/public/explorer/projects", params={"page_size": 51}).status_code == 422
    assert client.get("/public/explorer/projects", params={"page": 0}).status_code == 422

    body = client.get(
        "/public/explorer/projects",
        params={"sort": "sanctioned_desc", "page_size": 10},
    ).json()
    amounts = [p["sanctioned_amount"] for p in body["items"] if p["sanctioned_amount"] is not None]
    assert amounts == sorted(amounts, reverse=True)


# ------------------------------------------------------------------- detail

def test_detail_resolves_canonical_id_with_slashes(client):
    resp = client.get(f"/public/explorer/projects/{quote(REAL_PROJECT_ID, safe='')}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_id"] == REAL_PROJECT_ID
    assert set(body.keys()) == SUMMARY_FIELDS | DETAIL_EXTRA_FIELDS
    _assert_no_internal_keys(body)


def test_every_listed_project_resolves_in_detail(client):
    """The dashboard/list universe and the detail universe are the same."""
    items = client.get("/public/explorer/projects", params={"page_size": 25}).json()["items"]
    for item in items:
        resp = client.get(f"/public/explorer/projects/{quote(item['project_id'], safe='')}")
        assert resp.status_code == 200, item["project_id"]


def test_unknown_project_is_404_without_internal_detail(client):
    resp = client.get("/public/explorer/projects/NOT/A/REAL/ID")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Project not found."}


def test_detail_never_reports_nan_or_placeholder_text(client):
    body = client.get(f"/public/explorer/projects/{quote(REAL_PROJECT_ID, safe='')}").json()
    for value in body.values():
        if isinstance(value, str):
            assert value.lower() not in {"nan", "none", "null", "undefined"}
    assert "NaN" not in (body.get("mp_name") or "")


# ---------------------------------------------------------------- aggregates

def test_summary_is_anonymous_and_consistent_with_insights(client):
    summary = client.get("/public/explorer/summary")
    assert summary.status_code == 200
    body = summary.json()
    insights = client.get("/public/insights").json()

    assert body["kpis"]["total_projects"] == insights["kpis"]["total_projects"]
    assert body["kpis"]["completed_projects"] == insights["kpis"]["completed_projects"]
    assert sum(s["count"] for s in body["status_distribution"]) == body["kpis"]["total_projects"]
    assert sum(c["count"] for c in body["by_category"]) == body["kpis"]["total_projects"]
    assert body["meta"]["total_projects"] == body["kpis"]["total_projects"]
    _assert_no_internal_keys(body)


def test_utilisation_is_like_for_like(client):
    body = client.get("/public/explorer/summary").json()
    u = body["utilisation"]
    assert u["projects_with_sanctioned_amount"] <= u["total_projects"]
    expected = u["expenditure_on_those_projects"] / u["sanctioned_amount"] * 100
    assert u["percent"] == pytest.approx(expected)
    # Expenditure on projects that have a sanctioned amount can never exceed
    # ALL recorded expenditure.
    assert u["expenditure_on_those_projects"] <= float(body["kpis"]["total_expenditure"]) + 1e-6


def test_scoped_summary_and_unknown_area(client):
    scoped = client.get("/public/explorer/summary", params={"state": "Bihar"})
    assert scoped.status_code == 200
    body = scoped.json()
    assert body["scope_state"] == "Bihar"
    assert body["by_district"]
    assert {r["state"] for r in body["by_state"]} == {"Bihar"}

    missing = client.get("/public/explorer/summary", params={"state": "Atlantis"})
    assert missing.status_code == 404


def test_areas_states_then_districts_with_filters(client):
    states = client.get("/public/explorer/areas").json()
    assert states["level"] == "state" and states["rows"]

    completed = client.get("/public/explorer/areas", params={"status": "Completed"}).json()
    all_total = sum(r["project_count"] for r in states["rows"])
    done_total = sum(r["project_count"] for r in completed["rows"])
    assert 0 < done_total < all_total

    districts = client.get("/public/explorer/areas", params={"state": "Bihar"}).json()
    assert districts["level"] == "district"
    assert client.get("/public/explorer/areas", params={"state": "Atlantis"}).status_code == 404


def test_meta_reports_only_real_freshness(client):
    body = client.get("/public/meta").json()
    assert body["total_projects"] > 0
    assert body["source_note"]
    # timestamps are either real ISO strings or null -- never placeholders
    for key in ("dataset_refreshed_at", "latest_record_date"):
        assert body[key] is None or body[key][:2] == "20"


# ------------------------------------------------------------ non-regression

def test_internal_routes_remain_protected(client):
    assert client.get("/projects").status_code == 401
    assert client.get("/dashboard/stats").status_code == 401
    assert client.get("/alerts").status_code in (401, 403)


def test_legacy_public_routes_still_work(client):
    assert client.get("/public/overview").status_code == 200
    assert client.get("/public/insights").status_code == 200
    assert client.get("/public/projects").status_code == 200