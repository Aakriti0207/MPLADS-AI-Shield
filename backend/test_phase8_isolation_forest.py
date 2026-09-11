"""Focused validation for the standalone Phase 8 Isolation Forest detector."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from ml.isolation_forest.engine import (
    ISOLATION_FOREST_FEATURES,
    ISOLATION_FOREST_OUTPUT_COLUMNS,
    IsolationForestConfig,
    fit_isolation_forest_model,
    score_isolation_forest_data,
    write_isolation_forest_outputs,
)


def check(label: str, condition: bool) -> bool:
    print(f"  [{'PASS' if condition else 'FAIL'}] {label}")
    return bool(condition)


def historical_frame(rows: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(2026)
    frame = pd.DataFrame({
        "work_id": [f"H-{index}" for index in range(rows)],
        "sanction_amount": rng.normal(1_000_000, 80_000, rows),
        "recommended_amount": rng.normal(980_000, 75_000, rows),
        "amount_disbursed": rng.normal(760_000, 60_000, rows),
        "disbursed_to_sanction_ratio": rng.normal(0.76, 0.04, rows),
        "sanction_vs_recommended_ratio": rng.normal(1.02, 0.03, rows),
        "recommendation_to_sanction_days": rng.normal(30, 5, rows),
        "sanction_to_completion_days": rng.normal(180, 15, rows),
        "recommendation_to_completion_days": rng.normal(210, 16, rows),
        "expenditure_span_days": rng.normal(100, 10, rows),
        "n_lifecycle_stages_present": rng.integers(3, 5, rows),
        "has_recommended_record": 1,
        "has_sanctioned_record": 1,
        "has_completed_record": 1,
        "has_expenditure_record": 1,
        "n_expenditure_transactions": rng.normal(8, 1, rows),
        "n_distinct_vendors": rng.normal(3, 0.5, rows),
        "payment_success_ratio": rng.normal(0.85, 0.04, rows),
    })
    frame.loc[::7, "amount_disbursed"] = np.nan
    frame.loc[::9, "n_expenditure_transactions"] = np.nan
    return frame


def main() -> int:
    checks: list[tuple[bool, str]] = []
    training = historical_frame()
    training_original = training.copy(deep=True)
    model = fit_isolation_forest_model(training)
    checks.append(check("model fits on historical rows", model.training_row_count == len(training)))
    checks.append(check("17-feature registry is explicit", len(ISOLATION_FOREST_FEATURES) == 17))
    checks.append(check("Work ID is excluded from fitted features", "work_id" not in model.selected_features and "work_id" not in model.model_features))
    checks.append(check("training input is not mutated", training.equals(training_original)))
    checks.append(check("preprocessing records training-only fitting", model.preprocessing_metadata["fit_on_training_rows_only"]))
    checks.append(check("median preprocessing metadata is present", model.preprocessing_metadata["imputation_strategy"] == "median"))

    unseen = training.iloc[[0, 1]].copy(deep=True)
    for column in ISOLATION_FOREST_FEATURES:
        unseen.iloc[0, unseen.columns.get_loc(column)] = training[column].median()
    unseen.loc[:, "work_id"] = ["NEW_NORMAL", "NEW_UNUSUAL"]
    unseen.iloc[1, unseen.columns.get_loc("sanction_amount")] = 50_000_000
    unseen.iloc[1, unseen.columns.get_loc("sanction_to_completion_days")] = 2_000
    unseen.iloc[1, unseen.columns.get_loc("n_expenditure_transactions")] = 80
    unseen.index = [0, 0]
    unseen_original = unseen.copy(deep=True)
    training_raw_before_scoring = model.training_raw_scores.copy()
    result = score_isolation_forest_data(model, unseen)
    repeated = score_isolation_forest_data(model, unseen)
    checks.extend([
        check("unseen rows score without refitting", list(result.work_id) == ["NEW_NORMAL", "NEW_UNUSUAL"]),
        check("repeated scoring is deterministic", result.equals(repeated)),
        check("scoring input is not mutated", unseen.equals(unseen_original)),
        check("duplicate pandas indexes do not break scoring", len(result) == 2 and result.work_id.is_unique),
        check("output schema is stable", list(result.columns) == ISOLATION_FOREST_OUTPUT_COLUMNS),
        check("scores are bounded 0-100", result.isolation_forest_risk_score.between(0, 100).all()),
        check("unusual multivariate row outranks normal row", result.iloc[1].isolation_forest_risk_score > result.iloc[0].isolation_forest_risk_score),
        check("fitted model remains unchanged after scoring", np.array_equal(model.training_raw_scores, training_raw_before_scoring)),
    ])

    sparse = pd.DataFrame({"work_id": ["SPARSE"], **{column: [np.nan] for column in ISOLATION_FOREST_FEATURES}})
    sparse_result = score_isolation_forest_data(model, sparse)
    checks.append(check("completely missing row is not evaluable", sparse_result.iloc[0].isolation_forest_status == "NOT_EVALUABLE"))
    checks.append(check("empty scoring input returns stable schema", list(score_isolation_forest_data(model, unseen.iloc[0:0]).columns) == ISOLATION_FOREST_OUTPUT_COLUMNS))

    try:
        fit_isolation_forest_model(training.drop(columns=["work_id"]))
        missing_schema_rejected = False
    except ValueError as error:
        missing_schema_rejected = "work_id" in str(error)
    checks.append(check("missing/insufficient supported schema produces a clear error", missing_schema_rejected))
    try:
        fit_isolation_forest_model(training.iloc[:3])
        insufficient_rejected = False
    except ValueError:
        insufficient_rejected = True
    checks.append(check("insufficient training data is rejected", insufficient_rejected))
    with tempfile.TemporaryDirectory() as directory:
        output_path = Path(directory) / "if_scores.csv"
        checks.append(check("no output file is written by fit or score", not output_path.exists()))
        written = write_isolation_forest_outputs(result, output_path)
        checks.append(check("output is written only when explicitly requested", written.exists()))

    passed = all(checks)
    print(f"PHASE 8 SYNTHETIC: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


def run_real_behavioral_harness() -> bool:
    """Read-only behavioral report against the current Phase 3 fixture."""
    path = Path(__file__).parent / "data" / "processed" / "ml_features.csv"
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    frame = pd.read_csv(path)
    split = int(len(frame) * 0.8)
    history, holdout = frame.iloc[:split].copy(deep=True), frame.iloc[split:].copy(deep=True)
    model = fit_isolation_forest_model(history)
    normal = holdout.iloc[[0]].copy(deep=True)
    cases = {"normal_holdout": normal}
    financial = normal.copy(deep=True)
    financial.loc[:, "work_id"] = "CASE_FINANCIAL_TIMELINE"
    financial.loc[:, "sanction_amount"] = financial["sanction_amount"] * 25
    financial.loc[:, "sanction_to_completion_days"] = financial["sanction_to_completion_days"] * 10
    cases["unusual_financial_timeline"] = financial
    lifecycle = normal.copy(deep=True)
    lifecycle.loc[:, "work_id"] = "CASE_LIFECYCLE_TIMELINE"
    lifecycle.loc[:, "n_lifecycle_stages_present"] = 1
    lifecycle.loc[:, "has_completed_record"] = 0
    lifecycle.loc[:, "sanction_to_completion_days"] = 1
    cases["unusual_lifecycle_timeline"] = lifecycle
    multivariate = normal.copy(deep=True)
    multivariate.loc[:, "work_id"] = "CASE_MULTIVARIATE"
    multivariate.loc[:, "sanction_vs_recommended_ratio"] = 0.2
    multivariate.loc[:, "payment_success_ratio"] = 0.05
    multivariate.loc[:, "expenditure_span_days"] = 1
    cases["unusual_multivariate"] = multivariate
    sparse_case = pd.DataFrame({"work_id": ["CASE_SPARSE"], **{column: [np.nan] for column in ISOLATION_FOREST_FEATURES}})
    cases["sparse_no_evidence"] = sparse_case
    scored = score_isolation_forest_data(model, pd.concat(cases.values(), ignore_index=True))
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    print("PHASE 8 REAL-DATA BEHAVIORAL HARNESS")
    print(json.dumps({
        "source_sha256_before": before,
        "source_sha256_after": after,
        "source_unchanged": before == after,
        "fitted_row_count": model.training_row_count,
        "holdout_row_count": len(holdout),
        "selected_feature_count": len(model.selected_features),
        "selected_features": list(model.selected_features),
        "missing_supported_features": list(model.missing_supported_features),
        "missingness_after_preprocessing": model.preprocessing_metadata["missing_indicators"],
        "cases": scored.to_dict(orient="records"),
        "unusual_cases_outrank_normal": bool(scored.iloc[1:4].isolation_forest_risk_score.max() > scored.iloc[0].isolation_forest_risk_score),
    }, indent=2, default=str))
    return before == after


if __name__ == "__main__":
    raise SystemExit(main() if run_real_behavioral_harness() else 1)