"""Phase 10 runner that executes the existing detectors on synthetic fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ml.anomalies.engine import build_phase5_outputs
from ml.compliance.engine import build_compliance_outputs
from ml.duplicates.engine import build_phase6_outputs
from ml.evaluation.synthetic import SCENARIO_IDS, scenario_inputs
from ml.features import build_ml_features
from ml.risk import build_output, validate_inputs


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "evaluation"


def execute_scenario(scenario_id: str) -> dict:
    canonical, target, metadata = scenario_inputs(scenario_id)
    features = build_ml_features(canonical)
    findings, compliance_summary = build_compliance_outputs(features)
    anomalies, phase5_summary = build_phase5_outputs(features)
    duplicate_matches, duplicate_summary = build_phase6_outputs(canonical)
    inputs = {
        "canonical": canonical[["work_id"]], "compliance_findings": findings,
        "compliance_summary": compliance_summary,
        "financial_anomalies": anomalies[anomalies["domain"].eq("FINANCIAL")].copy(),
        "timeline_anomalies": anomalies[anomalies["domain"].eq("TIMELINE")].copy(),
        "phase5_summary": phase5_summary, "duplicate_matches": duplicate_matches,
        "duplicate_summary": duplicate_summary,
    }
    validate_inputs(inputs)
    risk_output = build_output(inputs)
    row = risk_output.loc[risk_output["work_id"].eq(target)].iloc[0]
    target_findings = findings[(findings["work_id"] == target) & (findings["status"] == "FLAG")]
    target_anomalies = anomalies[(anomalies["work_id"] == target) & (anomalies["status"] == "ANOMALY")]
    target_matches = duplicate_matches[duplicate_matches[["work_id_a", "work_id_b"]].isin([target]).any(axis=1)]
    detectors = []
    actual_flag = False
    if not target_anomalies.empty:
        domains = set(target_anomalies["domain"])
        if "FINANCIAL" in domains:
            detectors.append("FINANCIAL_ANOMALY")
        if "TIMELINE" in domains:
            detectors.append("TIMELINE_ANOMALY")
        actual_flag = True
    if not target_findings.empty:
        detectors.append("COMPLIANCE")
        actual_flag = True
    if not target_matches.empty:
        detectors.append("DUPLICATE")
        actual_flag = True
    actual_detector = "+".join(detectors) if detectors else "NONE"
    reasons = " ".join(str(row[column]) for column in ("top_reason_1", "top_reason_2", "top_reason_3") if pd.notna(row[column]))
    expected_flag = metadata.expected_detector not in {"NONE", "MISSING_DATA", "ZERO_VALUE"}
    explanation_ok = scenario_id in {"CLEAN_CONTROL", "MISSING_DATA", "ZERO_VALUE"}
    if scenario_id == "FINANCIAL_ANOMALY":
        explanation_ok = "financial" in reasons.lower() or "expenditure" in reasons.lower()
    elif scenario_id == "TIMELINE_ANOMALY":
        explanation_ok = "completion period" in reasons.lower() or "timeline" in reasons.lower()
    elif scenario_id == "COMPLIANCE_VIOLATION":
        explanation_ok = "expenditure exceeds sanction" in reasons.lower()
    elif scenario_id == "DUPLICATE_SIMILARITY":
        explanation_ok = "match" in reasons.lower() or "duplicate" in reasons.lower()
    elif scenario_id == "MULTI_EVIDENCE":
        explanation_ok = "expenditure" in reasons.lower() and "duration" in reasons.lower()
    elif scenario_id == "INVALID_DATE_ORDER":
        explanation_ok = "completion occurred before sanction" in reasons.lower()
    if scenario_id == "RISK_EXPLANATION":
        explanation_ok = "expenditure" in reasons.lower() or "financial" in reasons.lower()
    passed = actual_flag == expected_flag and explanation_ok
    if scenario_id == "CLEAN_CONTROL":
        passed = not actual_flag and float(row["risk_score"]) == 0.0
    if scenario_id == "MISSING_DATA":
        c_flags = set(target_findings["rule_id"])
        passed = target_anomalies.empty and not {"C08", "C09"}.intersection(c_flags)
    if scenario_id == "ZERO_VALUE":
        passed = bool(features.loc[features["work_id"].eq(target), "total_expenditure"].iloc[0] == 0.0) and target_findings[target_findings["rule_id"].isin(["C08", "C09"])].empty
    expected_risk_change = "0.0" if scenario_id == "CLEAN_CONTROL" else "> 0.0"
    return {
        "scenario_id": scenario_id, "work_id": target, "description": metadata.description,
        "expected_detector": metadata.expected_detector, "actual_detector": actual_detector,
        "expected_flag": expected_flag, "actual_flag": actual_flag,
        "expected_risk_behavior": "positive risk when evidence exists" if expected_flag else "no artificial risk",
        "expected_risk_change": expected_risk_change,
        "actual_risk_change": float(row["risk_score"]), "expected_reason": metadata.expected_reason,
        "actual_reason": reasons, "explanation_ok": explanation_ok,
        "one_row_per_work_id": risk_output["work_id"].is_unique,
        "risk_score_in_range": bool(risk_output["risk_score"].between(0, 100).all()),
        "pass": bool(passed), "risk_output": risk_output,
    }


def run_evaluation(output_dir: Path | str | None = DEFAULT_OUTPUT_DIR) -> tuple[pd.DataFrame, dict]:
    results = [execute_scenario(scenario_id) for scenario_id in SCENARIO_IDS]
    rows = [{key: value for key, value in result.items() if key != "risk_output"} for result in results]
    result_frame = pd.DataFrame(rows)
    repeat = [execute_scenario(scenario_id) for scenario_id in SCENARIO_IDS]
    deterministic = all(a["risk_output"].equals(b["risk_output"]) for a, b in zip(results, repeat))
    single_signal_score = float(result_frame.loc[result_frame["scenario_id"] == "FINANCIAL_ANOMALY", "actual_risk_change"].iloc[0])
    multi_signal_score = float(result_frame.loc[result_frame["scenario_id"] == "MULTI_EVIDENCE", "actual_risk_change"].iloc[0])
    multi_evidence_increases = multi_signal_score > single_signal_score
    result_frame.loc[result_frame["scenario_id"] == "MULTI_EVIDENCE", "pass"] &= multi_evidence_increases
    summary = {
        "evaluation_type": "SYNTHETIC_EVALUATION",
        "total_scenarios": len(result_frame), "passed_scenarios": int(result_frame["pass"].sum()),
        "failed_scenarios": int((~result_frame["pass"]).sum()),
        "pass_rate": float(result_frame["pass"].mean()),
        "expected_anomaly_detections": int(result_frame["expected_flag"].sum()),
        "actual_anomaly_detections": int(result_frame["actual_flag"].sum()),
        "false_positives_on_clean_controls": int(result_frame.loc[result_frame["scenario_id"] == "CLEAN_CONTROL", "actual_flag"].sum()),
        "explanation_coverage": float(result_frame["explanation_ok"].mean()),
        "multi_evidence_increases_over_single_signal": multi_evidence_increases,
        "deterministic": deterministic,
        "final_status": "PASS" if bool(result_frame["pass"].all()) and deterministic else "FAIL",
        "limitations": "Synthetic controlled scenarios validate pipeline behavior, not real-world fraud accuracy.",
    }
    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        result_frame.to_csv(output_dir / "phase10_scenario_results.csv", index=False)
        (output_dir / "phase10_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        report = "# Phase 10 Synthetic Evaluation\n\nThis evaluates controlled anomalies through the existing Phase 3-7 pipeline. It is not real-world accuracy.\n\n"
        report += "| Scenario | Expected detector | Actual detector | Expected flag | Actual flag | Risk score | Pass |\n| --- | --- | --- | ---: | ---: | ---: | ---: |\n"
        for _, item in result_frame.iterrows():
            report += f"| {item['scenario_id']} | {item['expected_detector']} | {item['actual_detector']} | {item['expected_flag']} | {item['actual_flag']} | {item['actual_risk_change']:.2f} | {item['pass']} |\n"
        report += f"\n\nFinal status: **{summary['final_status']}**\n"
        (output_dir / "phase10_report.md").write_text(report, encoding="utf-8")
    return result_frame, summary


if __name__ == "__main__":
    frame, summary = run_evaluation()
    print(json.dumps(summary, indent=2))