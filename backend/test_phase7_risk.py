"""Synthetic validation for Phase 7 (Risk Fusion Engine).

Follows the same convention as test_phase4_compliance.py / test_phase5_
anomalies.py / test_phase6_duplicates.py: synthetic, deterministic inputs
built directly as DataFrames (matching the real Phase 4/5/6 output schemas),
a flat list of (passed, label) checks, and a PASS/FAIL summary.

Run with: python test_phase7_risk.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from ml.risk import (
    OUTPUT_COLUMNS,
    build_output,
    generate_quality_report,
    validate_inputs,
    write_risk_outputs,
)
from ml.risk_config import (
    DATA_QUALITY_CAP,
    evidence_status_for,
    risk_level_for,
)


# ---------------------------------------------------------------------------
# Fixture builders -- mirror the real Phase 2/4/5/6 CSV schemas exactly.
# ---------------------------------------------------------------------------

def _canonical(work_ids: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"work_id": work_ids})


def _compliance_summary(work_ids: list[str], not_evaluable: set[str] = frozenset()) -> pd.DataFrame:
    return pd.DataFrame({
        "work_id": work_ids,
        "compliance_status": ["NOT_EVALUABLE" if w in not_evaluable else "PASS" for w in work_ids],
    })


def _compliance_finding(work_id: str, rule_id: str, category: str, status: str, severity: str, message: str) -> dict:
    return {
        "work_id": work_id, "rule_id": rule_id, "category": category,
        "status": status, "severity": severity, "message": message,
        "evidence_json": "{}",
    }


def _phase5_summary(work_ids: list[str], evaluated: dict[str, tuple[int, int]] | None = None) -> pd.DataFrame:
    evaluated = evaluated or {}
    rows = []
    for w in work_ids:
        fin_eval, tl_eval = evaluated.get(w, (0, 0))
        rows.append({
            "work_id": w, "financial_metrics_evaluated": fin_eval, "financial_anomaly_count": 0,
            "timeline_metrics_evaluated": tl_eval, "timeline_anomaly_count": 0, "total_anomaly_count": 0,
            "financial_not_evaluable_count": 0, "timeline_not_evaluable_count": 0,
            "phase5_status": "NOT_EVALUABLE" if fin_eval == 0 and tl_eval == 0 else "NO_ANOMALY_FOUND",
        })
    return pd.DataFrame(rows)


def _anomaly_row(work_id: str, metric_name: str, domain: str, status: str, observed_value, modified_z_score,
                  direction: str = "HIGH", decision_method: str = "modified_z_score",
                  peer_group_level: str = "state", peer_group_key: str = "State A") -> dict:
    return {
        "work_id": work_id, "metric_name": metric_name, "domain": domain, "status": status,
        "observed_value": observed_value, "transformed_value": observed_value,
        "peer_group_level": peer_group_level, "peer_group_key": peer_group_key, "peer_group_size": 25,
        "peer_median": 100.0, "peer_mad": 5.0, "peer_q1": 90.0, "peer_q3": 110.0,
        "modified_z_score": modified_z_score, "lower_bound": None, "upper_bound": None,
        "direction": direction, "decision_method": decision_method, "evidence_json": "{}",
    }


def _empty_anomalies(domain: str) -> pd.DataFrame:
    columns = [
        "work_id", "metric_name", "domain", "status", "observed_value", "transformed_value",
        "peer_group_level", "peer_group_key", "peer_group_size", "peer_median", "peer_mad",
        "peer_q1", "peer_q3", "modified_z_score", "lower_bound", "upper_bound", "direction",
        "decision_method", "evidence_json",
    ]
    return pd.DataFrame(columns=columns)


def _duplicate_summary(work_ids: list[str], statuses: dict[str, tuple[int, int, float | None, str]] | None = None) -> pd.DataFrame:
    statuses = statuses or {}
    rows = []
    for w in work_ids:
        exact, similar, highest, status = statuses.get(w, (0, 0, None, "NO_MATCH_FOUND"))
        rows.append({
            "work_id": w, "exact_match_count": exact, "similar_match_count": similar,
            "highest_similarity_score": highest, "phase6_status": status,
        })
    return pd.DataFrame(rows)


def _empty_matches() -> pd.DataFrame:
    columns = [
        "work_id_a", "work_id_b", "match_type", "similarity_score",
        "description_quality_a", "description_quality_b", "description_frequency_a",
        "description_frequency_b", "same_state", "same_constituency", "same_mp",
        "same_implementing_agency", "financial_year_a", "financial_year_b",
        "financial_year_relationship", "recommended_amount_difference",
        "sanction_amount_difference", "evidence_json",
    ]
    return pd.DataFrame(columns=columns)


def _match_row(work_id_a: str, work_id_b: str, match_type: str, similarity_score: float,
                freq_a: int = 1, freq_b: int = 1) -> dict:
    return {
        "work_id_a": work_id_a, "work_id_b": work_id_b, "match_type": match_type,
        "similarity_score": similarity_score, "description_quality_a": "USABLE",
        "description_quality_b": "USABLE", "description_frequency_a": freq_a,
        "description_frequency_b": freq_b, "same_state": True, "same_constituency": True,
        "same_mp": True, "same_implementing_agency": True, "financial_year_a": "2024-2025",
        "financial_year_b": "2024-2025", "financial_year_relationship": "SAME",
        "recommended_amount_difference": 0.0, "sanction_amount_difference": 0.0, "evidence_json": "{}",
    }


def make_inputs(
    work_ids: list[str],
    compliance_findings: list[dict] | None = None,
    compliance_not_evaluable: set[str] = frozenset(),
    financial_rows: list[dict] | None = None,
    timeline_rows: list[dict] | None = None,
    phase5_evaluated: dict[str, tuple[int, int]] | None = None,
    duplicate_matches: list[dict] | None = None,
    duplicate_statuses: dict[str, tuple[int, int, float | None, str]] | None = None,
) -> dict[str, pd.DataFrame]:
    """Assemble a full Phase 7 input dict from synthetic per-phase fixtures."""
    findings = pd.DataFrame(compliance_findings) if compliance_findings else pd.DataFrame(
        columns=["work_id", "rule_id", "category", "status", "severity", "message", "evidence_json"]
    )
    financial = pd.DataFrame(financial_rows) if financial_rows else _empty_anomalies("FINANCIAL")
    timeline = pd.DataFrame(timeline_rows) if timeline_rows else _empty_anomalies("TIMELINE")
    matches = pd.DataFrame(duplicate_matches) if duplicate_matches else _empty_matches()
    return {
        "canonical": _canonical(work_ids),
        "compliance_findings": findings,
        "compliance_summary": _compliance_summary(work_ids, compliance_not_evaluable),
        "financial_anomalies": financial,
        "timeline_anomalies": timeline,
        "phase5_summary": _phase5_summary(work_ids, phase5_evaluated),
        "duplicate_matches": matches,
        "duplicate_summary": _duplicate_summary(work_ids, duplicate_statuses),
    }


def row_for(output: pd.DataFrame, work_id: str) -> pd.Series:
    matches = output.loc[output["work_id"] == work_id]
    assert len(matches) == 1, f"expected exactly one row for {work_id}, found {len(matches)}"
    return matches.iloc[0]


def main() -> int:
    checks: list[tuple[bool, str]] = []

    def check(condition: bool, label: str) -> None:
        checks.append((bool(condition), label))

    # ------------------------------------------------------------------
    # 1. No evidence at all -> no artificial risk; evidence_status reflects
    #    insufficient evidence, not "safe."
    # ------------------------------------------------------------------
    inputs = make_inputs(
        ["W_NONE"],
        compliance_not_evaluable={"W_NONE"},
        duplicate_statuses={"W_NONE": (0, 0, None, "NOT_EVALUABLE")},
    )
    validate_inputs(inputs)
    output = build_output(inputs)
    row = row_for(output, "W_NONE")
    check(row["risk_score"] == 0.0, "1. no evidence -> risk_score is 0")
    check(row["evidence_status"] == "INSUFFICIENT", "1. no evidence -> evidence_status is INSUFFICIENT")
    check(row["total_evidence_signals"] == 0, "1. no evidence -> zero evidence signals")

    # ------------------------------------------------------------------
    # 2. HIGH compliance evidence materially increases risk.
    # ------------------------------------------------------------------
    inputs = make_inputs(
        ["W_HIGH_COMPLIANCE"],
        compliance_findings=[_compliance_finding(
            "W_HIGH_COMPLIANCE", "C08", "FINANCIAL", "FLAG", "HIGH",
            "Total expenditure exceeds sanction: total_expenditure exceeds sanction_amount.",
        )],
    )
    output = build_output(inputs)
    row = row_for(output, "W_HIGH_COMPLIANCE")
    check(row["compliance_contribution"] >= 10.0, "2. HIGH compliance FLAG contributes >= 10 points")
    check(row["risk_score"] > 0.0, "2. HIGH compliance evidence increases risk_score above 0")
    check(row["has_compliance_signal"], "2. has_compliance_signal is True")

    # ------------------------------------------------------------------
    # 3. Financial anomaly increases risk.
    # ------------------------------------------------------------------
    inputs = make_inputs(
        ["W_FIN_ANOMALY"],
        financial_rows=[_anomaly_row("W_FIN_ANOMALY", "total_expenditure", "FINANCIAL", "ANOMALY", 500000.0, 6.0)],
        phase5_evaluated={"W_FIN_ANOMALY": (1, 0)},
    )
    output = build_output(inputs)
    row = row_for(output, "W_FIN_ANOMALY")
    check(row["financial_anomaly_contribution"] > 0.0, "3. financial anomaly contributes > 0 points")
    check(row["has_financial_anomaly"], "3. has_financial_anomaly is True")

    # ------------------------------------------------------------------
    # 4. Timeline anomaly increases risk.
    # ------------------------------------------------------------------
    inputs = make_inputs(
        ["W_TL_ANOMALY"],
        timeline_rows=[_anomaly_row("W_TL_ANOMALY", "sanction_to_completion_days", "TIMELINE", "ANOMALY", 900.0, 6.0)],
        phase5_evaluated={"W_TL_ANOMALY": (0, 1)},
    )
    output = build_output(inputs)
    row = row_for(output, "W_TL_ANOMALY")
    check(row["timeline_anomaly_contribution"] > 0.0, "4. timeline anomaly contributes > 0 points")
    check(row["has_timeline_anomaly"], "4. has_timeline_anomaly is True")

    # ------------------------------------------------------------------
    # 5. Duplicate candidate increases risk appropriately, without implying
    #    confirmed fraud/duplication.
    # ------------------------------------------------------------------
    inputs = make_inputs(
        ["W_DUP_A", "W_DUP_B"],
        duplicate_matches=[_match_row("W_DUP_A", "W_DUP_B", "SIMILAR_MATCH", 0.92, freq_a=2, freq_b=2)],
        duplicate_statuses={
            "W_DUP_A": (0, 1, 0.92, "SIMILAR_WORK_CANDIDATE"),
            "W_DUP_B": (0, 1, 0.92, "SIMILAR_WORK_CANDIDATE"),
        },
    )
    output = build_output(inputs)
    row = row_for(output, "W_DUP_A")
    check(row["duplicate_contribution"] > 0.0, "5. duplicate candidate contributes > 0 points")
    check("not a confirmed duplicate" in (row["top_reason_1"] or ""), "5. duplicate reason does not claim confirmed fraud/duplication")
    check("W_DUP_B" in (row["top_reason_1"] or ""), "5. duplicate reason names the matched Work ID")

    # ------------------------------------------------------------------
    # 6. Multiple independent evidence types outrank a single weak signal.
    # ------------------------------------------------------------------
    single_weak_inputs = make_inputs(
        ["W_SINGLE_WEAK"],
        compliance_findings=[_compliance_finding(
            "W_SINGLE_WEAK", "C10", "FINANCIAL", "FLAG", "WARNING",
            "Sanction is below the normal minimum of Rs 2.5 lakh.",
        )],
    )
    multi_inputs = make_inputs(
        ["W_MULTI"],
        compliance_findings=[_compliance_finding(
            "W_MULTI", "C10", "FINANCIAL", "FLAG", "WARNING",
            "Sanction is below the normal minimum of Rs 2.5 lakh.",
        )],
        financial_rows=[_anomaly_row("W_MULTI", "total_expenditure", "FINANCIAL", "ANOMALY", 500000.0, 6.0)],
        timeline_rows=[_anomaly_row("W_MULTI", "sanction_to_completion_days", "TIMELINE", "ANOMALY", 900.0, 6.0)],
        phase5_evaluated={"W_MULTI": (1, 1)},
    )
    weak_score = row_for(build_output(single_weak_inputs), "W_SINGLE_WEAK")["risk_score"]
    multi_score = row_for(build_output(multi_inputs), "W_MULTI")["risk_score"]
    check(multi_score > weak_score, "6. multiple independent evidence types score higher than a single weak signal")

    # ------------------------------------------------------------------
    # 7. Missing evidence does not automatically become LOW/safe -- the
    #    evidence_status field must independently flag it as INSUFFICIENT
    #    rather than being folded into the risk level.
    # ------------------------------------------------------------------
    inputs = make_inputs(
        ["W_MISSING", "W_CLEAN"],
        compliance_not_evaluable={"W_MISSING"},
        duplicate_statuses={"W_MISSING": (0, 0, None, "NOT_EVALUABLE")},
    )
    output = build_output(inputs)
    missing_row = row_for(output, "W_MISSING")
    clean_row = row_for(output, "W_CLEAN")
    check(missing_row["risk_level"] == "LOW", "7. missing-evidence project scores LOW (no fabricated risk)")
    check(missing_row["evidence_status"] == "INSUFFICIENT", "7. missing-evidence project is flagged INSUFFICIENT, distinct from a clean LOW")
    check(clean_row["evidence_status"] != "INSUFFICIENT", "7. a project with evaluable-but-clean evidence is not INSUFFICIENT")

    # ------------------------------------------------------------------
    # 8. Missing expenditure (NOT_EVALUABLE / NaN observed value) is never
    #    treated as zero and never contributes anomaly points.
    # ------------------------------------------------------------------
    inputs = make_inputs(
        ["W_MISSING_EXP"],
        financial_rows=[_anomaly_row(
            "W_MISSING_EXP", "total_expenditure", "FINANCIAL", "NOT_EVALUABLE",
            None, None, decision_method="not_evaluable",
        )],
        phase5_evaluated={"W_MISSING_EXP": (0, 0)},
    )
    output = build_output(inputs)
    row = row_for(output, "W_MISSING_EXP")
    check(row["financial_anomaly_contribution"] == 0.0, "8. NOT_EVALUABLE financial row contributes zero, never treated as an anomaly")

    # ------------------------------------------------------------------
    # 9. A data-quality signal alone does not dominate real anomaly
    #    evidence.
    # ------------------------------------------------------------------
    dq_only_inputs = make_inputs(
        ["W_DQ_ONLY"],
        compliance_findings=[_compliance_finding(
            "W_DQ_ONLY", "DQ01", "DATA_QUALITY", "FLAG", "WARNING",
            "Source fields conflict and require data-quality review; this is not a compliance violation.",
        )],
    )
    dq_row = row_for(build_output(dq_only_inputs), "W_DQ_ONLY")
    check(dq_row["data_quality_contribution"] <= DATA_QUALITY_CAP, "9. data_quality_contribution never exceeds its cap")
    check(dq_row["risk_score"] < multi_score, "9. data-quality-only signal scores below a multi-category anomaly case")

    # ------------------------------------------------------------------
    # 10. Overlapping compliance + financial evidence does not double count.
    # ------------------------------------------------------------------
    overlap_inputs = make_inputs(
        ["W_OVERLAP"],
        compliance_findings=[_compliance_finding(
            "W_OVERLAP", "C08", "FINANCIAL", "FLAG", "HIGH",
            "Total expenditure exceeds sanction: total_expenditure exceeds sanction_amount.",
        )],
        financial_rows=[_anomaly_row("W_OVERLAP", "expenditure_to_sanction_ratio", "FINANCIAL", "ANOMALY", 2.5, 6.0)],
        phase5_evaluated={"W_OVERLAP": (1, 0)},
    )
    no_overlap_inputs = make_inputs(
        ["W_NO_OVERLAP"],
        financial_rows=[_anomaly_row("W_NO_OVERLAP", "expenditure_to_sanction_ratio", "FINANCIAL", "ANOMALY", 2.5, 6.0)],
        phase5_evaluated={"W_NO_OVERLAP": (1, 0)},
    )
    overlap_row = row_for(build_output(overlap_inputs), "W_OVERLAP")
    no_overlap_row = row_for(build_output(no_overlap_inputs), "W_NO_OVERLAP")
    check(
        overlap_row["financial_anomaly_contribution"] < no_overlap_row["financial_anomaly_contribution"],
        "10. overlapping C08 + financial anomaly discounts the anomaly's contribution vs. the same anomaly alone",
    )
    check(
        overlap_row["risk_score"] < overlap_row["compliance_contribution"] + no_overlap_row["financial_anomaly_contribution"] + 0.01,
        "10. fused score for the overlapping case is less than naively summing both signals at full weight",
    )

    # ------------------------------------------------------------------
    # 11. Risk score bounds hold even for a maximal synthetic worst case.
    # ------------------------------------------------------------------
    max_findings = [
        _compliance_finding("W_MAX", rule_id, "LIFECYCLE" if rule_id.startswith("C0") and rule_id in {"C03", "C04", "C05", "C06", "C07"} else "FINANCIAL", "FLAG", "HIGH", "x")
        for rule_id in ["C03", "C04", "C05", "C06", "C07", "C08", "C09"]
    ] + [
        _compliance_finding("W_MAX", rule_id, "TIMELINE" if rule_id in {"C01", "C02"} else "FINANCIAL", "FLAG", "WARNING", "x")
        for rule_id in ["C01", "C02", "C10", "C11"]
    ] + [_compliance_finding("W_MAX", "DQ01", "DATA_QUALITY", "FLAG", "WARNING", "x")]
    max_financial = [_anomaly_row("W_MAX", metric, "FINANCIAL", "ANOMALY", 1e9, 500.0) for metric in [
        "recommended_amount", "sanction_amount", "amount_disbursed", "total_expenditure",
        "total_amount_in_progress", "sanction_vs_recommended_ratio", "sanction_minus_recommended_amount",
        "disbursed_to_sanction_ratio", "expenditure_to_sanction_ratio", "in_progress_amount_to_sanction_ratio",
    ]]
    max_timeline = [_anomaly_row("W_MAX", metric, "TIMELINE", "ANOMALY", 5000.0, 500.0) for metric in [
        "recommendation_to_sanction_days", "sanction_to_completion_days", "recommendation_to_completion_days",
        "recommendation_to_first_expenditure_days", "sanction_to_first_expenditure_days", "expenditure_span_days",
    ]]
    max_inputs = make_inputs(
        ["W_MAX"],
        compliance_findings=max_findings,
        financial_rows=max_financial,
        timeline_rows=max_timeline,
        phase5_evaluated={"W_MAX": (10, 6)},
        duplicate_matches=[_match_row("W_MAX", "W_MAX_PARTNER", "EXACT_MATCH", 1.0, freq_a=2, freq_b=2)],
        duplicate_statuses={"W_MAX": (1, 0, 1.0, "EXACT_MATCH_CANDIDATE")},
    )
    max_row = row_for(build_output(max_inputs), "W_MAX")
    check(0.0 <= max_row["risk_score"] <= 100.0, "11. maximal synthetic worst case stays within [0, 100]")
    check(not np.isnan(max_row["risk_score"]) and np.isfinite(max_row["risk_score"]), "11. risk_score is never NaN or infinite")

    # ------------------------------------------------------------------
    # 12. Risk threshold mapping is correct at configured boundaries.
    # ------------------------------------------------------------------
    check(risk_level_for(0.0) == "LOW", "12. score 0 maps to LOW")
    check(risk_level_for(24.99) == "LOW", "12. score just under 25 maps to LOW")
    check(risk_level_for(25.0) == "MEDIUM", "12. score 25 maps to MEDIUM")
    check(risk_level_for(49.99) == "MEDIUM", "12. score just under 50 maps to MEDIUM")
    check(risk_level_for(50.0) == "HIGH", "12. score 50 maps to HIGH")
    check(risk_level_for(74.99) == "HIGH", "12. score just under 75 maps to HIGH")
    check(risk_level_for(75.0) == "CRITICAL", "12. score 75 maps to CRITICAL")
    check(risk_level_for(100.0) == "CRITICAL", "12. score 100 maps to CRITICAL")
    check(evidence_status_for(0) == "INSUFFICIENT", "12. 0 evaluable domains maps to INSUFFICIENT")
    check(evidence_status_for(2) == "LIMITED", "12. 2 evaluable domains maps to LIMITED")
    check(evidence_status_for(4) == "SUFFICIENT", "12. 4 evaluable domains maps to SUFFICIENT")

    # ------------------------------------------------------------------
    # 13. Determinism: identical input -> identical output.
    # ------------------------------------------------------------------
    repeat_a = build_output(multi_inputs)
    repeat_b = build_output(multi_inputs)
    check(repeat_a.equals(repeat_b), "13. running Phase 7 twice on the same input produces an identical result")

    # ------------------------------------------------------------------
    # 14. Exactly one row per Work ID; no duplicates.
    # ------------------------------------------------------------------
    combined_inputs = make_inputs(["W_A", "W_B", "W_C"])
    combined_output = build_output(combined_inputs)
    check(list(combined_output.columns) == OUTPUT_COLUMNS, "14. output schema matches OUTPUT_COLUMNS exactly")
    check(combined_output["work_id"].is_unique, "14. no duplicate Work IDs in output")
    check(set(combined_output["work_id"]) == {"W_A", "W_B", "W_C"}, "14. output has exactly one row per input Work ID")

    # ------------------------------------------------------------------
    # 15. Explanation coverage: every project with a non-zero contribution
    #     has at least one corresponding reason.
    # ------------------------------------------------------------------
    coverage_output = build_output(multi_inputs)
    coverage_row = row_for(coverage_output, "W_MULTI")
    has_any_contribution = any(
        coverage_row[column] > 0 for column in [
            "compliance_contribution", "financial_anomaly_contribution",
            "timeline_anomaly_contribution", "duplicate_contribution", "data_quality_contribution",
        ]
    )
    check(
        (not has_any_contribution) or coverage_row["top_reason_1"] not in (None, ""),
        "15. a project with any non-zero contribution has a top_reason_1",
    )
    summary = json.loads(coverage_row["source_signal_summary"])
    check(len(summary["signals"]) >= 2, "15. source_signal_summary lists traceable signals for a multi-evidence project")

    # ------------------------------------------------------------------
    # 16. Duplicate evidence preserves matched Work ID and similarity score.
    # ------------------------------------------------------------------
    dup_summary = json.loads(row_for(build_output(inputs=make_inputs(
        ["W_DUP_A2", "W_DUP_B2"],
        duplicate_matches=[_match_row("W_DUP_A2", "W_DUP_B2", "SIMILAR_MATCH", 0.97, freq_a=2, freq_b=2)],
        duplicate_statuses={
            "W_DUP_A2": (0, 1, 0.97, "SIMILAR_WORK_CANDIDATE"),
            "W_DUP_B2": (0, 1, 0.97, "SIMILAR_WORK_CANDIDATE"),
        },
    )), "W_DUP_A2")["source_signal_summary"])
    duplicate_signal = next((s for s in dup_summary["signals"] if s["source"] == "duplicate"), None)
    check(duplicate_signal is not None, "16. duplicate signal is present in source_signal_summary")

    # ------------------------------------------------------------------
    # 17. Writing Phase 7 outputs never overwrites earlier phase outputs.
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as directory:
        directory_path = Path(directory)
        sentinel_files = [
            "canonical_projects.csv", "ml_features.csv", "compliance_findings.csv",
            "compliance_summary.csv", "financial_anomalies.csv", "timeline_anomalies.csv",
            "duplicate_matches.csv", "duplicate_summary.csv",
        ]
        for name in sentinel_files:
            (directory_path / name).write_text("sentinel_content_untouched\n")
        report = generate_quality_report(combined_output)
        write_risk_outputs(combined_output, report, directory_path)
        unchanged = all((directory_path / name).read_text() == "sentinel_content_untouched\n" for name in sentinel_files)
        check(unchanged, "17. Phase 7 write never modifies earlier-phase output files")
        check((directory_path / "project_risk_scores.csv").exists(), "17. project_risk_scores.csv is written")
        check((directory_path / "risk_quality_report.json").exists(), "17. risk_quality_report.json is written")

    for passed, label in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    passed_all = all(passed for passed, _ in checks)
    print(f"PHASE 7: {'PASS' if passed_all else 'FAIL'}")
    return 0 if passed_all else 1


if __name__ == "__main__":
    raise SystemExit(main())