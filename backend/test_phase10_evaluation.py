"""Synthetic evaluation of the existing MPLADS AI Shield detectors."""

from pathlib import Path

from ml.evaluation.runner import execute_scenario, run_evaluation
from ml.evaluation.synthetic import SCENARIO_IDS


def test_required_scenarios_pass():
    results, summary = run_evaluation(output_dir=None)
    assert set(results["scenario_id"]) == set(SCENARIO_IDS)
    assert summary["final_status"] == "PASS", results.loc[~results["pass"]].to_dict("records")


def test_clean_missing_zero_and_explanation_contracts():
    assert execute_scenario("CLEAN_CONTROL")["actual_flag"] is False
    assert execute_scenario("MISSING_DATA")["pass"]
    assert execute_scenario("ZERO_VALUE")["pass"]
    assert execute_scenario("RISK_EXPLANATION")["explanation_ok"]


def test_output_shape_and_bounds():
    for scenario_id in SCENARIO_IDS:
        result = execute_scenario(scenario_id)
        output = result["risk_output"]
        assert output["work_id"].is_unique
        assert output["risk_score"].between(0, 100).all()


def test_runner_does_not_need_production_outputs(tmp_path: Path):
    _, summary = run_evaluation(tmp_path)
    assert summary["deterministic"]
    assert (tmp_path / "phase10_scenario_results.csv").exists()
    assert (tmp_path / "phase10_summary.json").exists()
    assert (tmp_path / "phase10_report.md").exists()