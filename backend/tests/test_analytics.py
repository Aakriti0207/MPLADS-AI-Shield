"""
Tests for the production analytics contract.

Analytics is intentionally sourced from:
    canonical_projects.csv + project_risk_scores.csv

The database is not the source of truth for analytics because the
production project universe is the canonical dataset.
"""

import pytest

from app.aggregations import (
    load_canonical_projects,
    load_risk_fusion,
    compute_core_totals_from_canonical,
    compute_risk_level_counts_from_risk_fusion,
)


def test_analytics_production_dataset_loads():
    canonical = load_canonical_projects()
    risk = load_risk_fusion()

    assert len(canonical) == 43863
    assert len(risk) == 43863

    assert canonical["work_id"].is_unique
    assert risk["work_id"].is_unique

    assert set(canonical["work_id"]) == set(risk["work_id"])


def test_analytics_core_totals_match_production_dataset():
    canonical = load_canonical_projects()

    totals = compute_core_totals_from_canonical(canonical)

    assert totals["total_projects"] == 43863
    assert totals["total_sanctioned_amount"] == pytest.approx(
        23048672771.579998
    )
    assert totals["total_expenditure"] == pytest.approx(
        3849817769.0
    )
    assert totals["average_financial_progress"] == pytest.approx(
        5.429794252929969
    )

    assert totals["average_physical_progress"] is None

    assert totals["active_projects"] == 20580
    assert totals["completed_projects"] == 23283

    # Completion-date data is not available in the canonical dataset.
    assert totals["delayed_projects"] == 0
    assert totals["delayed_projects_available"] is False
    assert (
        totals["delayed_projects_reason"]
        == "Expected completion data is not available in canonical_projects.csv."
    )


def test_analytics_risk_counts_match_risk_fusion():
    risk = load_risk_fusion()

    counts = compute_risk_level_counts_from_risk_fusion(risk)

    assert counts == {
        "LOW": 42174,
        "MEDIUM": 1684,
        "HIGH": 5,
        "CRITICAL": 0,
    }


def test_analytics_status_distribution_matches_canonical():
    canonical = load_canonical_projects()

    status_counts = canonical["status"].value_counts(dropna=False).to_dict()

    assert status_counts == {
        "COMPLETED": 23283,
        "SANCTIONED": 8109,
        "ONGOING": 6428,
        "NOT_SPECIFIED": 6043,
    }


def test_analytics_risk_scores_are_available_for_entire_universe():
    risk = load_risk_fusion()

    assert risk["risk_score"].notna().all()
    assert risk["risk_level"].notna().all()

    assert len(risk) == 43863


def test_analytics_risk_levels_are_valid():
    risk = load_risk_fusion()

    allowed_levels = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

    assert set(risk["risk_level"].dropna().unique()).issubset(
        allowed_levels
    )


def test_analytics_has_no_duplicate_project_ids():
    canonical = load_canonical_projects()
    risk = load_risk_fusion()

    assert canonical["work_id"].nunique() == len(canonical)
    assert risk["work_id"].nunique() == len(risk)


def test_analytics_canonical_and_risk_universes_match_exactly():
    canonical = load_canonical_projects()
    risk = load_risk_fusion()

    canonical_ids = set(canonical["work_id"])
    risk_ids = set(risk["work_id"])

    assert canonical_ids == risk_ids


def test_analytics_financial_progress_is_reasonable():
    canonical = load_canonical_projects()

    totals = compute_core_totals_from_canonical(canonical)

    assert totals["average_financial_progress"] >= 0
    assert totals["average_financial_progress"] <= 100


def test_analytics_production_status_counts_sum_to_total():
    canonical = load_canonical_projects()

    status_counts = canonical["status"].value_counts(dropna=False)

    assert status_counts.sum() == 43863


def test_analytics_production_risk_counts_sum_to_total():
    risk = load_risk_fusion()

    counts = compute_risk_level_counts_from_risk_fusion(risk)

    assert sum(counts.values()) == 43863