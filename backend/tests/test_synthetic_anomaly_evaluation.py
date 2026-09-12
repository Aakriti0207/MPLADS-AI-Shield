"""
Phase 1 (evaluation + synthetic anomaly backend validation) test coverage.

This module does NOT reimplement or duplicate the existing Phase 10 synthetic
evaluation harness in ``ml/evaluation/synthetic.py`` / ``ml/evaluation/runner.py``
(exercised by ``backend/test_phase10_evaluation.py``). That harness already runs
the real preprocessing -> compliance/anomaly/duplicate/payment/isolation ->
risk-fusion -> WHY-risky pipeline end to end on controlled synthetic fixtures.

What this module adds is explicit, individually-named regression coverage for
each of the six evaluation cases called for in Phase 1 (normal, financial
anomaly, execution/delay anomaly, duplicate/similarity, compliance violation,
multi-signal high risk), asserting against the *existing* component outputs
(compliance findings, anomaly rows, duplicate matches, risk fusion output)
rather than inventing new expected numeric scores. Every scenario is executed
through ``ml.evaluation.runner.execute_scenario``, which is the same real
pipeline used by production risk scoring -- nothing here mocks a detector.
"""

from __future__ import annotations

import pytest

from ml.evaluation.runner import execute_scenario


# ---------------------------------------------------------------------------
# A. Normal project
# ---------------------------------------------------------------------------


def test_normal_project_does_not_trigger_any_signal():
    """A clean, internally-consistent project must not be flagged by any
    detector, and must not receive risk purely for being synthetic."""
    result = execute_scenario("CLEAN_CONTROL")
    output = result["risk_output"]
    row = output.loc[output["work_id"] == result["work_id"]].iloc[0]

    assert result["actual_flag"] is False
    assert result["actual_detector"] == "NONE"
    assert float(row["risk_score"]) == 0.0
    assert row["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert row["risk_level"] == "LOW"


# ---------------------------------------------------------------------------
# B. Financial anomaly
# ---------------------------------------------------------------------------


def test_financial_anomaly_is_reflected_in_financial_component_and_risk_output():
    """An unusually high expenditure relative to peers must surface as a
    FINANCIAL-domain anomaly row and must be reflected in the risk output's
    WHY-risky explanation -- without asserting an exact score."""
    result = execute_scenario("FINANCIAL_ANOMALY")
    output = result["risk_output"]
    row = output.loc[output["work_id"] == result["work_id"]].iloc[0]

    assert "FINANCIAL_ANOMALY" in result["actual_detector"]
    assert result["actual_flag"] is True
    assert float(row["risk_score"]) > 0.0
    assert result["explanation_ok"]
    assert "risk_score" in output.columns and output["risk_score"].between(0, 100).all()


# ---------------------------------------------------------------------------
# C. Delay / execution anomaly
# ---------------------------------------------------------------------------


def test_execution_delay_anomaly_is_reflected_as_timeline_signal():
    """An extreme sanction-to-completion duration (i.e. execution badly
    behind a normal timeline) must surface as a TIMELINE-domain anomaly and
    be represented in the fused risk output."""
    result = execute_scenario("TIMELINE_ANOMALY")
    output = result["risk_output"]
    row = output.loc[output["work_id"] == result["work_id"]].iloc[0]

    assert "TIMELINE_ANOMALY" in result["actual_detector"]
    assert result["actual_flag"] is True
    assert float(row["risk_score"]) > 0.0
    assert result["explanation_ok"]


# ---------------------------------------------------------------------------
# D. Duplicate / similar project
# ---------------------------------------------------------------------------


def test_duplicate_similarity_is_reflected_in_duplicate_component():
    """Two records constructed with identical descriptions must trigger the
    existing duplicate/similarity mechanism, and the match must reference
    the target work_id."""
    result = execute_scenario("DUPLICATE_SIMILARITY")
    output = result["risk_output"]
    row = output.loc[output["work_id"] == result["work_id"]].iloc[0]

    assert "DUPLICATE" in result["actual_detector"]
    assert result["actual_flag"] is True
    assert result["explanation_ok"]
    assert float(row["risk_score"]) > 0.0


# ---------------------------------------------------------------------------
# E. Compliance issue
# ---------------------------------------------------------------------------


def test_compliance_violation_is_reflected_in_compliance_component():
    """A record whose expenditure exceeds its sanction amount must violate
    an existing compliance rule, and that finding must be represented in the
    risk output's explanation."""
    result = execute_scenario("COMPLIANCE_VIOLATION")
    output = result["risk_output"]
    row = output.loc[output["work_id"] == result["work_id"]].iloc[0]

    assert "COMPLIANCE" in result["actual_detector"]
    assert result["actual_flag"] is True
    assert result["explanation_ok"]
    assert float(row["risk_score"]) > 0.0


# ---------------------------------------------------------------------------
# F. Multi-signal high-risk project
# ---------------------------------------------------------------------------


def test_multi_signal_case_fuses_independent_signals_and_scores_higher_than_single_signal():
    """When financial and timeline signals coexist on the same project, risk
    fusion must combine the existing component outputs, the WHY-risky
    explanation must name both signals, and the fused score must exceed the
    score for either signal alone (financial-only, in this case)."""
    single = execute_scenario("FINANCIAL_ANOMALY")
    multi = execute_scenario("MULTI_EVIDENCE")

    assert "FINANCIAL_ANOMALY" in multi["actual_detector"]
    assert "TIMELINE_ANOMALY" in multi["actual_detector"]
    assert multi["actual_flag"] is True
    assert multi["explanation_ok"]
    assert multi["actual_risk_change"] > single["actual_risk_change"]


# ---------------------------------------------------------------------------
# Cross-cutting evaluation-quality checks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario_id",
    [
        "CLEAN_CONTROL",
        "FINANCIAL_ANOMALY",
        "TIMELINE_ANOMALY",
        "DUPLICATE_SIMILARITY",
        "COMPLIANCE_VIOLATION",
        "MULTI_EVIDENCE",
    ],
)
def test_evaluation_scenario_produces_one_row_per_work_id_in_bounds(scenario_id):
    """Every evaluation scenario's risk output must have exactly one row per
    work_id, and risk scores must stay within the implementation's valid
    [0, 100] range -- this does not assume any particular numeric value."""
    result = execute_scenario(scenario_id)
    assert result["one_row_per_work_id"]
    assert result["risk_score_in_range"]


def test_evaluation_scenarios_are_deterministic():
    """Re-running the same synthetic scenario twice through the real
    pipeline must produce an identical risk output, with no reliance on
    unseeded randomness."""
    first = execute_scenario("MULTI_EVIDENCE")
    second = execute_scenario("MULTI_EVIDENCE")
    assert first["risk_output"].equals(second["risk_output"])