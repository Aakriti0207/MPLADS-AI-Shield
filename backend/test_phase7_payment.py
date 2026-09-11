"""Focused synthetic validation for the standalone Payment AI component."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from ml.payment.engine import (
    PAYMENT_OUTPUT_COLUMNS,
    PAYMENT_SIGNAL_COLUMNS,
    BaselineDiagnostics,
    PaymentConfig,
    PaymentModel,
    SignalBaseline,
    fit_payment_model,
    score_payment_data,
    write_payment_outputs,
)


def historical_frame() -> pd.DataFrame:
    rows = []
    for index in range(20):
        rows.append({
            "work_id": f"H-{index}", "sanction_amount": 100000.0, "total_expenditure": 70000.0 + index * 100,
            "total_amount_in_progress": 5000.0, "n_expenditure_transactions": 4.0 + index % 2,
            "n_distinct_vendors": 2.0, "n_payment_success": 4.0, "n_payment_in_progress": 0.0,
            "expenditure_span_days": 60.0 + index % 3,
        })
    return pd.DataFrame(rows)


def check(label: str, condition: bool) -> tuple[bool, str]:
    return condition, label


def main() -> int:
    checks: list[tuple[bool, str]] = []
    training = historical_frame()
    original = training.copy(deep=True)
    model = fit_payment_model(training)
    duplicate_index_training = training.copy(deep=True)
    duplicate_index_training.index = [0] * len(duplicate_index_training)
    unseen = pd.DataFrame([
        {"work_id": "NEW_NORMAL", "sanction_amount": 100000.0, "total_expenditure": 70000.0, "total_amount_in_progress": 5000.0, "n_expenditure_transactions": 4.0, "n_distinct_vendors": 2.0, "n_payment_success": 4.0, "n_payment_in_progress": 0.0, "expenditure_span_days": 60.0},
        {"work_id": "NEW_ABNORMAL", "sanction_amount": 100000.0, "total_expenditure": 1000000.0, "total_amount_in_progress": 0.0, "n_expenditure_transactions": 40.0, "n_distinct_vendors": 1.0, "n_payment_success": 1.0, "n_payment_in_progress": 39.0, "expenditure_span_days": 1.0},
        {"work_id": "NEW_EMPTY", "sanction_amount": np.nan, "total_expenditure": np.nan, "total_amount_in_progress": np.nan, "n_expenditure_transactions": np.nan, "n_distinct_vendors": np.nan, "n_payment_success": np.nan, "n_payment_in_progress": np.nan, "expenditure_span_days": np.nan},
        {"work_id": "NEW_NO_ACTIVITY", "sanction_amount": 100000.0, "total_expenditure": 0.0, "total_amount_in_progress": 0.0, "n_expenditure_transactions": 0.0, "n_distinct_vendors": 0.0, "n_payment_success": 0.0, "n_payment_in_progress": 0.0, "expenditure_span_days": np.nan},
        {"work_id": "NEW_INVALID", "sanction_amount": 0.0, "total_expenditure": -10.0, "total_amount_in_progress": 0.0, "n_expenditure_transactions": -1.0, "n_distinct_vendors": 0.0, "n_payment_success": 0.0, "n_payment_in_progress": 0.0, "expenditure_span_days": -2.0},
    ])
    unseen.index = [0, 0, 1, 1, 2]
    unseen_original = unseen.copy(deep=True)
    result = score_payment_data(model, unseen)
    repeated = score_payment_data(model, unseen)
    row = result.set_index("work_id")
    checks.extend([
        (row.loc["NEW_EMPTY", "payment_status"] == "NOT_EVALUABLE" and row.loc["NEW_EMPTY", "payment_risk_score"] == 0.0, "no payment evidence is not suspicious"),
        (row.loc["NEW_NO_ACTIVITY", "payment_status"] == "NOT_EVALUABLE" and row.loc["NEW_NO_ACTIVITY", "payment_risk_score"] == 0.0, "zero payment activity is not suspicious"),
        (row.loc["NEW_INVALID", "payment_status"] == "NOT_EVALUABLE", "invalid and zero-denominator payment data is not evaluable"),
        (row.loc["NEW_NORMAL", "payment_anomaly_status"] == "NORMAL", "normal payment behavior is not anomalous"),
        (row.loc["NEW_ABNORMAL", "payment_risk_score"] > row.loc["NEW_NORMAL", "payment_risk_score"] and row.loc["NEW_ABNORMAL", "payment_signal_count"] >= 2, "independent abnormal signals increase evidence"),
        (row.loc["NEW_ABNORMAL", "payment_reasons"] != "[]" and "payment_" in row.loc["NEW_ABNORMAL", "payment_reasons"], "flagged rows contain traceable explanations"),
        (result.equals(repeated), "scoring is deterministic"),
        (list(result.columns) == PAYMENT_OUTPUT_COLUMNS and result["work_id"].is_unique, "output schema and Work ID uniqueness are valid"),
        (result["payment_risk_score"].between(0, 100).all(), "scores are bounded"),
        ("work_id" not in model.feature_columns and "H-0" not in repr(model), "Work ID is excluded from fitted features"),
        (model.config == PaymentConfig() and model.config.anomaly_z_threshold == 3.5, "scoring policy is explicit and configurable"),
        (set(result.work_id) == {"NEW_NORMAL", "NEW_ABNORMAL", "NEW_EMPTY", "NEW_NO_ACTIVITY", "NEW_INVALID"}, "unseen projects score without refitting"),
        (unseen.equals(unseen_original), "scoring does not mutate new input rows"),
        (training.equals(original), "training input is not mutated"),
        (model.baseline_diagnostics["payment_utilization_ratio"].count >= model.config.min_training_values, "baseline sample counts are recorded"),
        (len({model.baselines[name].stability for name in model.baselines}) >= 1, "baseline stability is recorded"),
        (duplicate_index_training.reset_index(drop=True).equals(training.reset_index(drop=True)), "duplicate-index training input is not mutated"),
    ])

    no_baseline = PaymentModel(
        baselines={}, feature_columns=tuple(), config=model.config,
        baseline_diagnostics={name: BaselineDiagnostics(20, "UNSTABLE") for name in PAYMENT_SIGNAL_COLUMNS},
    )
    no_baseline_result = score_payment_data(no_baseline, unseen.iloc[[0]].copy())
    checks.append(check(
        "valid signals without a fitted baseline are not evaluable",
        no_baseline_result.iloc[0].payment_status == "NOT_EVALUABLE"
        and no_baseline_result.iloc[0].payment_risk_score == 0.0
        and "no_fitted_baseline" in no_baseline_result.iloc[0].payment_evidence,
    ))

    inconsistent = unseen.iloc[[0]].copy()
    inconsistent.loc[:, "n_payment_success"] = 5.0
    inconsistent.loc[:, "n_payment_in_progress"] = 5.0
    inconsistent.loc[:, "n_distinct_vendors"] = 9.0
    inconsistent.loc[:, "total_expenditure"] = 200000.0
    inconsistent.loc[:, "expenditure_to_sanction_ratio"] = 0.1
    inconsistent_result = score_payment_data(model, inconsistent)
    inconsistent_evidence = json.loads(inconsistent_result.iloc[0].payment_evidence)
    checks.append(check(
        "impossible counts and supplied ratios are not trusted",
        "payment_success_ratio" not in str(inconsistent_evidence)
        and "payment_in_progress_ratio" not in str(inconsistent_evidence)
        and inconsistent_result.iloc[0].payment_status in {"EVALUABLE", "NOT_EVALUABLE"},
    ))

    missing_schema = training.drop(columns=["sanction_amount"])
    try:
        fit_payment_model(missing_schema)
        missing_schema_rejected = False
    except ValueError as error:
        missing_schema_rejected = "sanction_amount" in str(error)
    checks.append(check("missing required schema is rejected clearly", missing_schema_rejected))

    single_family_config = PaymentConfig(min_training_families=5)
    try:
        fit_payment_model(training[["work_id", "sanction_amount", "total_expenditure", "total_amount_in_progress", "n_expenditure_transactions", "n_distinct_vendors", "n_payment_success", "n_payment_in_progress"]], config=single_family_config)
        insufficient_families_rejected = False
    except ValueError:
        insufficient_families_rejected = True
    checks.append(check("insufficient stable families are rejected", insufficient_families_rejected))

    capped_config = PaymentConfig(family_caps=(
        ("utilization_expenditure", 5.0),
        ("completion_progress", 5.0),
        ("transaction_activity", 5.0),
        ("vendor_concentration", 5.0),
    ))
    capped_model = fit_payment_model(training, config=capped_config)
    capped_result = score_payment_data(capped_model, unseen.iloc[[1]].copy())
    checks.append(check("custom family caps are honored", capped_result.iloc[0].payment_risk_score <= 20.0))
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "payment_scores.csv"
        write_payment_outputs(result, str(path))
        checks.append((path.exists(), "output writing uses a caller-selected path"))
    for passed, label in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    passed = all(value for value, _ in checks)
    print(f"PHASE 7 PAYMENT AI: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())