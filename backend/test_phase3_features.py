"""Phase 3 validation: run with ``python test_phase3_features.py``."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features import (
    CANONICAL_INPUT_PATH,
    DATA_QUALITY_COLUMNS,
    FORBIDDEN_OUTPUT_COLUMNS,
    FORBIDDEN_RISK_MARKERS,
    RAW_CATEGORICAL_COLUMNS,
    build_ml_features,
    write_ml_features,
)


def check(name: str, condition: bool) -> bool:
    print(f"  [{'PASS' if condition else 'FAIL'}] {name}")
    return condition


def edge_case_rows(canonical: pd.DataFrame) -> pd.DataFrame:
    """Use actual canonical columns with controlled, non-risk edge cases."""
    rows = canonical.iloc[:3].copy(deep=True)
    rows.loc[:, "recommended_amount"] = [100.0, np.nan, 100.0]
    rows.loc[:, "sanction_amount"] = [200.0, 0.0, 50.0]
    rows.loc[:, "amount_disbursed"] = [100.0, np.nan, 25.0]
    rows.loc[:, "total_expenditure"] = [50.0, np.nan, 20.0]
    rows.loc[:, "total_amount_in_progress"] = [25.0, np.nan, 10.0]
    rows.loc[:, "n_expenditure_transactions"] = [2.0, np.nan, 2.0]
    rows.loc[:, "n_distinct_vendors"] = [1.0, np.nan, 1.0]
    rows.loc[:, "n_payment_success"] = [1.0, np.nan, 1.0]
    rows.loc[:, "n_payment_in_progress"] = [1.0, np.nan, 1.0]
    rows.loc[:, "recommended_date"] = ["2024-01-01", None, "2024-02-01"]
    rows.loc[:, "sanction_date"] = ["2024-01-01", "2024-01-02", "2024-01-01"]
    rows.loc[:, "completion_date"] = ["2024-01-01", None, "2023-12-31"]
    rows.loc[:, "first_expenditure_date"] = ["2024-01-01", None, "2024-01-02"]
    rows.loc[:, "last_expenditure_date"] = ["2024-01-01", None, "2024-01-03"]
    return rows


def main() -> int:
    canonical = pd.read_csv(CANONICAL_INPUT_PATH)
    original = canonical.copy(deep=True)
    features = build_ml_features(canonical)
    edge_features = build_ml_features(edge_case_rows(canonical))

    print("PHASE 3 FEATURE VALIDATION")
    checks = [
        check("same number of rows as canonical input", len(features) == len(canonical)),
        check("work_id remains unique", features["work_id"].is_unique),
        check("feature generation does not mutate canonical input", canonical.equals(original)),
        check("no duplicate feature columns", features.columns.is_unique),
        check(
            "no risk-score or label columns",
            not any(marker in column.lower() for column in features.columns for marker in FORBIDDEN_RISK_MARKERS)
            and not FORBIDDEN_OUTPUT_COLUMNS.intersection(features.columns),
        ),
        check(
            "no infinite numeric values",
            not np.isinf(features.select_dtypes(include=[np.number]).to_numpy(dtype=float)).any(),
        ),
        check(
            "all intended numeric features have numeric dtypes",
            all(pd.api.types.is_numeric_dtype(features[c]) for c in features.columns
                if c not in {"work_id", *RAW_CATEGORICAL_COLUMNS}),
        ),
        check(
            "Phase 2 data-quality/lifecycle flags are preserved",
            all((features[c].to_numpy() == canonical[c].astype(bool).astype("int8").to_numpy()).all() for c in DATA_QUALITY_COLUMNS),
        ),
        check("equal dates yield zero days", edge_features.loc[0, "recommendation_to_sanction_days"] == 0),
        check("missing dates yield missing durations", pd.isna(edge_features.loc[1, "recommendation_to_sanction_days"])),
        check("reversed dates remain negative", edge_features.loc[2, "recommendation_to_sanction_days"] < 0),
        check("zero denominator yields missing ratio", pd.isna(edge_features.loc[1, "expenditure_to_sanction_ratio"])),
        check("missing numerator yields missing ratio", pd.isna(edge_features.loc[1, "disbursed_to_sanction_ratio"])),
        check("valid ratio is calculated", edge_features.loc[0, "sanction_vs_recommended_ratio"] == 2.0),
    ]

    output_path = write_ml_features(features)
    checks.append(check("generated feature CSV was written", output_path.exists()))
    passed = all(checks)
    print(f"PHASE 3: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
