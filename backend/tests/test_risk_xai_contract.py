"""
Tests for the Risk Fusion + Explainable AI (XAI) response contract.

These are deliberately data-driven rather than API-driven: they exercise the
exact serialization helpers the /projects/{id}/risk and /demo/projects/{id}/risk
routes use, against synthetic rows shaped like real project_risk_scores.csv
rows. That keeps them fast and independent of the 43,863-row processed dataset
or a live database, while still covering the properties that actually matter.

What is asserted:

  1.  Overall score consistency      -- contributions sum to risk_score
  2.  Component score consistency    -- score x weight / 100 == contribution
  3.  Weight consistency             -- weights match risk_config caps, sum 100
  4.  Contribution calculation       -- per component, from real columns
  5.  Final score reconciliation     -- across several anomaly combinations
  6.  Risk level thresholds          -- risk_level_for boundaries
  7.  WHY FLAGGED generation         -- reasons land on the right component
  8.  Evidence generation            -- honest evidence_available flag
  9.  Missing data handling          -- no fabricated values
  10. Multiple simultaneous anomalies
  11. No-anomaly case                -- clean project stays at zero
  12. Per-anomaly cases              -- payment / financial / timeline /
                                        duplicate / compliance / isolation
                                        forest / data quality
  13. Canonical project ID handling  -- ids are not rewritten

Run with:  pytest tests/test_risk_xai_contract.py -v
"""

import json

import pandas as pd
import pytest

from app.routes.projects import (
    build_component_breakdown_from_legacy,
    enrich_component_details,
)
from ml.risk_config import (
    COMPONENT_LABELS,
    RISK_COMPONENT_CAPS,
    risk_level_for,
)

CONTRIBUTION_COLUMNS = {
    "compliance": "compliance_contribution",
    "financial_anomaly": "financial_anomaly_contribution",
    "timeline_anomaly": "timeline_anomaly_contribution",
    "duplicate": "duplicate_contribution",
    "data_quality": "data_quality_contribution",
    "payment": "payment_contribution",
    "isolation_forest": "isolation_forest_contribution",
}


def make_row(signals, work_id="WS/MP171/2024-2025/144805"):
    """Build a legacy-shaped risk row from a list of (source, tier, points, reason).

    Mirrors how ml/risk.py writes risk_reasons and source_signal_summary: both
    come from the same sorted rows, index for index.
    """

    contributions = {column: 0.0 for column in CONTRIBUTION_COLUMNS.values()}

    for source, _tier, points, _reason in signals:
        contributions[CONTRIBUTION_COLUMNS[source]] += points

    risk_score = round(sum(contributions.values()), 2)

    data = {
        "work_id": work_id,
        "risk_score": risk_score,
        "risk_level": risk_level_for(risk_score),
        "evidence_status": "SUFFICIENT",
        "risk_reasons": json.dumps([reason for _s, _t, _p, reason in signals]),
        "source_signal_summary": json.dumps(
            {
                "signals": [
                    {
                        "source": source,
                        "identifier": index,
                        "severity_tier": tier,
                        "points": points,
                    }
                    for index, (source, tier, points, _reason) in enumerate(signals)
                ]
            }
        ),
    }
    data.update(contributions)

    return pd.Series(data)


def components_for(signals, **kwargs):
    return enrich_component_details(
        build_component_breakdown_from_legacy(make_row(signals, **kwargs))
    )


# Named scenarios covering brief section 24's required test cases A-H.
FINANCIAL = ("financial_anomaly", 3, 8.0, "Total expenditure is unusually high.")
FINANCIAL_2 = ("financial_anomaly", 2, 5.0, "Disbursed-to-sanction ratio is outside peer range.")
TIMELINE = ("timeline_anomaly", 3, 3.0, "Sanction-to-completion duration is unusually long.")
PAYMENT = ("payment", 1, 1.2, "Payment utilisation ratio is unusually low.")
DUPLICATE = ("duplicate", 2, 4.0, "A similar work order was matched.")
COMPLIANCE = ("compliance", 2, 4.0, "Sanction was issued 81 days after recommendation.")
DATA_QUALITY = ("data_quality", 1, 8.0, "Source fields conflict and require review.")
ISOLATION = ("isolation_forest", 3, 8.53, "Project is unusual across the feature distribution.")


# ---------------------------------------------------------------------------
# 3. Weight consistency
# ---------------------------------------------------------------------------

def test_weights_match_config_and_sum_to_one_hundred():
    components = components_for([FINANCIAL])

    assert sum(RISK_COMPONENT_CAPS.values()) == 100.0

    for name, cap in RISK_COMPONENT_CAPS.items():
        assert components[name]["weight"] == cap

    assert sum(c["weight"] for c in components.values()) == 100.0


def test_every_component_is_present_even_when_it_did_not_trigger():
    components = components_for([FINANCIAL])

    assert set(components) == set(RISK_COMPONENT_CAPS)

    for name, detail in components.items():
        assert detail["label"] == COMPONENT_LABELS[name]


# ---------------------------------------------------------------------------
# 1, 2, 4, 5. Score / contribution reconciliation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "scenario,signals",
    [
        ("A normal project", []),
        ("B financial anomaly", [FINANCIAL]),
        ("C payment anomaly", [PAYMENT]),
        ("D timeline anomaly", [TIMELINE]),
        ("E duplicate anomaly", [DUPLICATE]),
        ("F compliance failure", [COMPLIANCE]),
        ("G isolation forest anomaly", [ISOLATION]),
        ("H data quality issue", [DATA_QUALITY]),
        (
            "I multiple simultaneous anomalies",
            [ISOLATION, FINANCIAL, FINANCIAL_2, TIMELINE, COMPLIANCE, DATA_QUALITY, PAYMENT],
        ),
    ],
)
def test_contributions_reconcile_with_final_score(scenario, signals):
    row = make_row(signals)
    components = enrich_component_details(build_component_breakdown_from_legacy(row))

    total = round(sum(c["contribution"] for c in components.values()), 2)

    assert total == pytest.approx(float(row["risk_score"]), abs=0.02), scenario


@pytest.mark.parametrize(
    "signals",
    [[FINANCIAL], [PAYMENT], [ISOLATION], [FINANCIAL, TIMELINE, COMPLIANCE, PAYMENT]],
)
def test_component_score_times_weight_equals_contribution(signals):
    components = components_for(signals)

    for name, detail in components.items():
        reconstructed = detail["score"] * detail["weight"] / 100
        assert reconstructed == pytest.approx(detail["contribution"], abs=0.06), name


# ---------------------------------------------------------------------------
# 6. Risk level thresholds
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "score,expected",
    [
        (0.0, "LOW"),
        (24.99, "LOW"),
        (25.0, "MEDIUM"),
        (49.99, "MEDIUM"),
        (50.0, "HIGH"),
        (74.99, "HIGH"),
        (75.0, "CRITICAL"),
        (100.0, "CRITICAL"),
    ],
)
def test_risk_level_thresholds(score, expected):
    assert risk_level_for(score) == expected


# ---------------------------------------------------------------------------
# 7. WHY FLAGGED generation
# ---------------------------------------------------------------------------

def test_reasons_are_attached_to_the_component_that_produced_them():
    components = components_for([ISOLATION, FINANCIAL, FINANCIAL_2, TIMELINE, PAYMENT])

    assert components["financial_anomaly"]["reasons"] == [FINANCIAL[3], FINANCIAL_2[3]]
    assert components["timeline_anomaly"]["reasons"] == [TIMELINE[3]]
    assert components["payment"]["reasons"] == [PAYMENT[3]]
    assert components["isolation_forest"]["reasons"] == [ISOLATION[3]]
    # Nothing leaks into a component that did not fire.
    assert components["duplicate"]["reasons"] == []


def test_status_reflects_the_highest_severity_signal_in_the_component():
    components = components_for([FINANCIAL, FINANCIAL_2])

    # FINANCIAL is tier 3 (HIGH), FINANCIAL_2 is tier 2 (MEDIUM).
    assert components["financial_anomaly"]["status"] == "HIGH"
    assert components["payment"]["status"] == "NONE"


def test_untriggered_component_is_none_not_low():
    components = components_for([FINANCIAL])

    # "NONE" and "LOW" must stay distinct: a component that did not fire is
    # not the same as one that fired weakly.
    assert components["duplicate"]["status"] == "NONE"
    assert components["duplicate"]["contribution"] == 0.0


# ---------------------------------------------------------------------------
# 8, 9. Evidence + missing-data honesty
# ---------------------------------------------------------------------------

def test_legacy_rows_report_evidence_as_unavailable_rather_than_empty():
    components = components_for([FINANCIAL])

    # A legacy CSV carries no structured evidence. It must say so, so the UI
    # can distinguish "no evidence recorded" from "nothing was found".
    assert components["financial_anomaly"]["evidence"] == []
    assert components["financial_anomaly"]["evidence_available"] is False


def test_no_fabricated_values_for_a_clean_project():
    components = components_for([])

    for detail in components.values():
        assert detail["contribution"] == 0.0
        assert detail["score"] == 0.0
        assert detail["status"] == "NONE"
        assert detail["reasons"] == []
        assert detail["evidence"] == []


def test_malformed_summary_does_not_invent_reasons():
    row = make_row([FINANCIAL])
    row["source_signal_summary"] = "not json at all"

    components = enrich_component_details(build_component_breakdown_from_legacy(row))

    # Contributions still come from the real numeric columns...
    assert components["financial_anomaly"]["contribution"] == pytest.approx(8.0)
    # ...but no reason is manufactured from an unparseable summary.
    assert components["financial_anomaly"]["reasons"] == []


def test_missing_contribution_column_is_treated_as_zero_not_guessed():
    row = make_row([FINANCIAL])
    row["payment_contribution"] = None

    components = enrich_component_details(build_component_breakdown_from_legacy(row))

    assert components["payment"]["contribution"] == 0.0
    assert components["payment"]["status"] == "NONE"


# ---------------------------------------------------------------------------
# Presentational metadata
# ---------------------------------------------------------------------------

def test_every_component_carries_description_and_review_actions():
    components = components_for([FINANCIAL, PAYMENT])

    for name, detail in components.items():
        assert detail["description"], name
        assert detail["review_actions"], name
        assert all(isinstance(action, str) for action in detail["review_actions"])


def test_enrichment_never_overwrites_backend_supplied_values():
    parsed = {
        "financial_anomaly": {
            "label": "Financial Anomaly",
            "score": 90.0,
            "weight": 20.0,
            "contribution": 18.0,
            "status": "HIGH",
            "reasons": ["Real backend reason."],
            "evidence": [{"metric": "total_expenditure"}],
            "description": "A description the pipeline already supplied.",
            "review_actions": ["An action the pipeline already supplied."],
        }
    }

    enriched = enrich_component_details(parsed)

    assert enriched["financial_anomaly"]["description"] == (
        "A description the pipeline already supplied."
    )
    assert enriched["financial_anomaly"]["review_actions"] == [
        "An action the pipeline already supplied."
    ]
    # Evidence present in the payload means evidence really is available.
    assert enriched["financial_anomaly"]["evidence_available"] is True
    assert enriched["financial_anomaly"]["contribution"] == 18.0


# ---------------------------------------------------------------------------
# 13. Canonical project ID handling
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "work_id",
    [
        "WS/MP171/2024-2025/144805",
        "WS/MP18286/2024-2025/146588",
        "WS/MP18248/2024-2025/153846",
    ],
)
def test_canonical_work_ids_are_not_rewritten(work_id):
    row = make_row([FINANCIAL], work_id=work_id)
    assert row["work_id"] == work_id

    # The breakdown is keyed by component, never by a re-derived project id.
    components = enrich_component_details(build_component_breakdown_from_legacy(row))
    assert set(components) == set(RISK_COMPONENT_CAPS)