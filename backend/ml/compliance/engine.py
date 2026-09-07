"""Execution, aggregation, and output writing for Phase 4."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ml.compliance.rules import FLAG, NOT_EVALUABLE, PASS, RULE_EVALUATORS, RULE_IDS
from ml.config import BACKEND_ROOT


FEATURE_INPUT_PATH = BACKEND_ROOT / "data" / "processed" / "ml_features.csv"
OUTPUT_DIR = BACKEND_ROOT / "data" / "processed"
FINDINGS_COLUMNS = ["work_id", "rule_id", "category", "status", "severity", "message", "evidence_json"]
SUMMARY_COLUMNS = ["work_id", "compliance_status", "high_severity_count", "warning_count", "data_quality_issue_count", "rules_evaluated", "rules_flagged"]

REQUIRED_COLUMNS = frozenset({
    "work_id", "recommended_amount", "sanction_amount", "amount_disbursed",
    "total_expenditure", "recommendation_to_sanction_days", "sanction_to_completion_days",
    "is_recommended_date_available", "is_sanction_date_available",
    "is_completion_date_available", "is_first_expenditure_date_available",
    "flag_completion_before_sanction", "flag_expenditure_before_recommendation",
    "flag_recommendation_after_sanction", "any_field_conflict",
})


def _validate_features(features: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_COLUMNS - set(features.columns))
    if missing:
        raise ValueError("Phase 3 features are missing required compliance columns: " + ", ".join(missing))
    if features["work_id"].isna().any() or not features["work_id"].is_unique:
        raise ValueError("Phase 3 features must have a non-null, unique work_id column")


def _status_for_project(findings: list[dict]) -> str:
    compliance = [finding for finding in findings if finding["category"] != "DATA_QUALITY"]
    if any(f["status"] == FLAG and f["severity"] == "HIGH" for f in compliance):
        return "REVIEW_REQUIRED"
    if any(f["status"] == FLAG and f["severity"] == "WARNING" for f in compliance):
        return "WARNING"
    if not any(f["status"] in {PASS, FLAG} for f in compliance):
        return "NOT_EVALUABLE"
    return "PASS"


def build_compliance_outputs(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate every rule without mutating ``features``."""
    _validate_features(features)
    findings = []
    summaries = []
    for _, row in features.copy(deep=True).iterrows():
        row_findings = [RULE_EVALUATORS[rule_id](row).as_dict() for rule_id in RULE_IDS]
        for finding in row_findings:
            finding["evidence_json"] = json.dumps(finding.pop("evidence"), sort_keys=True, allow_nan=False)
        findings.extend(row_findings)
        compliance_findings = [f for f in row_findings if f["category"] != "DATA_QUALITY"]
        summaries.append({
            "work_id": str(row["work_id"]),
            "compliance_status": _status_for_project(row_findings),
            "high_severity_count": sum(f["status"] == FLAG and f["severity"] == "HIGH" for f in compliance_findings),
            "warning_count": sum(f["status"] == FLAG and f["severity"] == "WARNING" for f in compliance_findings),
            "data_quality_issue_count": sum(f["status"] == FLAG and f["category"] == "DATA_QUALITY" for f in row_findings),
            "rules_evaluated": sum(f["status"] in {PASS, FLAG} for f in compliance_findings),
            "rules_flagged": sum(f["status"] == FLAG for f in row_findings),
        })
    return pd.DataFrame(findings, columns=FINDINGS_COLUMNS), pd.DataFrame(summaries, columns=SUMMARY_COLUMNS)


def run_compliance_from_file(path: Path | str = FEATURE_INPUT_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    return build_compliance_outputs(pd.read_csv(path))


def write_compliance_outputs(
    findings: pd.DataFrame,
    summary: pd.DataFrame,
    output_dir: Path | str = OUTPUT_DIR,
) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    findings_path = output_dir / "compliance_findings.csv"
    summary_path = output_dir / "compliance_summary.csv"
    findings.to_csv(findings_path, index=False)
    summary.to_csv(summary_path, index=False)
    return findings_path, summary_path