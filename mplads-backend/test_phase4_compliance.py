"""Synthetic validation for the deterministic Phase 4 compliance engine."""

from __future__ import annotations

import json
import tempfile

import numpy as np
import pandas as pd

from ml.compliance.engine import build_compliance_outputs, write_compliance_outputs


BASE = {
    "work_id": "WS/MP1/2024-2025/1", "recommended_amount": 500000.0,
    "sanction_amount": 500000.0, "amount_disbursed": 400000.0,
    "total_expenditure": 300000.0, "recommendation_to_sanction_days": 30.0,
    "sanction_to_completion_days": 300.0, "is_recommended_date_available": 1,
    "is_sanction_date_available": 1, "is_completion_date_available": 1,
    "is_first_expenditure_date_available": 1, "flag_completion_before_sanction": 0,
    "flag_expenditure_before_recommendation": 0, "flag_recommendation_after_sanction": 0,
    "any_field_conflict": 0,
}


def row(**changes):
    value = BASE.copy()
    value.update(changes)
    return value


def finding(findings, work_id, rule_id):
    return findings[(findings.work_id == work_id) & (findings.rule_id == rule_id)].iloc[0]


def main() -> int:
    rows = [
        row(),
        row(work_id="WS/MP1/2024-2025/2", recommendation_to_sanction_days=46),
        row(work_id="WS/MP1/2024-2025/3", sanction_to_completion_days=366),
        row(work_id="WS/MP1/2024-2025/4", is_sanction_date_available=0),
        row(work_id="WS/MP1/2024-2025/5", total_expenditure=1, is_sanction_date_available=0),
        row(work_id="WS/MP1/2024-2025/6", flag_completion_before_sanction=1),
        row(work_id="WS/MP1/2024-2025/7", flag_expenditure_before_recommendation=1),
        row(work_id="WS/MP1/2024-2025/8", flag_recommendation_after_sanction=1),
        row(work_id="WS/MP1/2024-2025/9", total_expenditure=600000),
        row(work_id="WS/MP1/2024-2025/10", amount_disbursed=600000),
        row(work_id="WS/MP1/2024-2025/11", sanction_amount=249999),
        row(work_id="WS/MP1/2024-2025/12", recommended_amount=400000, sanction_amount=500000),
        row(work_id="WS/MP1/2024-2025/13", any_field_conflict=1),
        row(work_id="WS/MP1/2024-2025/14", recommendation_to_sanction_days=np.nan, is_recommended_date_available=0, is_sanction_date_available=0, sanction_amount=np.nan),
        row(work_id="WS/MP1/2024-2025/15", recommendation_to_sanction_days=-2, flag_recommendation_after_sanction=1),
    ]
    features = pd.DataFrame(rows)
    original = features.copy(deep=True)
    findings, summary = build_compliance_outputs(features)

    checks = [
        (finding(findings, rows[0]["work_id"], "C01").status == "PASS", "clean C01 passes"),
        (finding(findings, rows[1]["work_id"], "C01").status == "FLAG", "C01 delayed flags"),
        (finding(findings, rows[2]["work_id"], "C02").status == "FLAG", "C02 delayed flags"),
        (finding(findings, rows[3]["work_id"], "C03").status == "FLAG", "C03 flags"),
        (finding(findings, rows[4]["work_id"], "C04").status == "FLAG", "C04 flags"),
        (finding(findings, rows[5]["work_id"], "C05").status == "FLAG", "C05 flags"),
        (finding(findings, rows[6]["work_id"], "C06").status == "FLAG", "C06 flags"),
        (finding(findings, rows[7]["work_id"], "C07").status == "FLAG", "C07 flags"),
        (finding(findings, rows[8]["work_id"], "C08").status == "FLAG", "C08 flags"),
        (finding(findings, rows[9]["work_id"], "C09").status == "FLAG", "C09 flags"),
        (finding(findings, rows[10]["work_id"], "C10").status == "FLAG", "C10 flags"),
        (finding(findings, rows[11]["work_id"], "C11").status == "FLAG", "C11 flags"),
        (finding(findings, rows[12]["work_id"], "DQ01").status == "FLAG", "DQ01 flags"),
        (finding(findings, rows[13]["work_id"], "C01").status == "NOT_EVALUABLE", "missing values are not evaluable"),
        (finding(findings, rows[14]["work_id"], "C01").status == "NOT_EVALUABLE", "negative duration is not evaluable"),
        (summary.work_id.is_unique and summary.work_id.tolist() == features.work_id.tolist(), "work IDs preserved"),
        (features.equals(original), "input is not mutated"),
        (not np.isinf(pd.to_numeric(findings.select_dtypes(exclude="object").stack(), errors="coerce").dropna()).any(), "no infinite outputs"),
        (all(json.loads(value) is not None for value in findings.evidence_json), "evidence is valid JSON"),
        (summary.loc[summary.work_id == rows[12]["work_id"], "compliance_status"].iloc[0] == "PASS", "DQ01 does not change compliance status"),
    ]
    with tempfile.TemporaryDirectory() as directory:
        findings_path, summary_path = write_compliance_outputs(findings, summary, directory)
        checks.extend([(findings_path.exists(), "findings CSV written"), (summary_path.exists(), "summary CSV written")])
    for passed, label in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    passed = all(passed for passed, _ in checks)
    print(f"PHASE 4: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())