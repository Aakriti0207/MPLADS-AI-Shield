from pathlib import Path
import pandas as pd

from ml.payment.engine import (
    fit_payment_model,
    score_payment_data,
    write_payment_outputs,
)

from ml.isolation_forest.engine import (
    fit_isolation_forest_model,
    score_isolation_forest_data,
    write_isolation_forest_outputs,
)


BASE_DIR = Path(__file__).resolve().parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"

FEATURES_PATH = PROCESSED_DIR / "ml_features.csv"
PAYMENT_OUTPUT = PROCESSED_DIR / "payment_scores.csv"
ISOLATION_OUTPUT = PROCESSED_DIR / "isolation_forest_scores.csv"


def main():
    print("=" * 70)
    print("MPLADS AI SHIELD — ML MODEL GENERATION")
    print("=" * 70)

    print("\n[1/3] Loading ML features...")
    features = pd.read_csv(FEATURES_PATH)

    print(f"Loaded: {len(features):,} rows x {len(features.columns)} columns")

    if "work_id" not in features.columns:
        raise ValueError("ml_features.csv is missing work_id")

    if features["work_id"].isna().any():
        raise ValueError("ml_features.csv contains null work_id values")

    if not features["work_id"].is_unique:
        raise ValueError("ml_features.csv contains duplicate work_id values")

    # ---------------------------------------------------------------
    # PAYMENT AI
    # ---------------------------------------------------------------

    print("\n[2/3] Running Payment AI...")

    payment_columns = [
        "work_id",
        "sanction_amount",
        "total_expenditure",
        "total_amount_in_progress",
        "n_expenditure_transactions",
        "n_distinct_vendors",
        "n_payment_success",
        "n_payment_in_progress",
        "expenditure_span_days",
    ]

    missing_payment = [
        column
        for column in payment_columns
        if column not in features.columns
    ]

    if missing_payment:
        raise ValueError(
            "ml_features.csv is missing Payment AI columns: "
            + ", ".join(missing_payment)
        )

    payment_input = features[payment_columns].copy()

    # Fit on the complete historical dataset.
    payment_model = fit_payment_model(payment_input)

    payment_result = score_payment_data(
        payment_model,
        payment_input,
    )

    write_payment_outputs(
        payment_result,
        PAYMENT_OUTPUT,
    )

    print(
        f"Payment AI output: "
        f"{len(payment_result):,} rows x "
        f"{len(payment_result.columns)} columns"
    )

    print(
        "Payment status counts:",
        payment_result["payment_status"].value_counts().to_dict(),
    )

    print(
        "Payment anomaly counts:",
        payment_result["payment_anomaly_status"].value_counts().to_dict(),
    )

    # ---------------------------------------------------------------
    # ISOLATION FOREST
    # ---------------------------------------------------------------

    print("\n[3/3] Running Isolation Forest...")

    isolation_model = fit_isolation_forest_model(features)

    isolation_result = score_isolation_forest_data(
        isolation_model,
        features,
    )

    write_isolation_forest_outputs(
        isolation_result,
        ISOLATION_OUTPUT,
    )

    print(
        f"Isolation Forest output: "
        f"{len(isolation_result):,} rows x "
        f"{len(isolation_result.columns)} columns"
    )

    print(
        "Isolation Forest status counts:",
        isolation_result["isolation_forest_status"].value_counts().to_dict(),
    )

    print("\n" + "=" * 70)
    print("ML MODEL GENERATION COMPLETE")
    print("=" * 70)

    print(f"\nCreated:")
    print(f"  {PAYMENT_OUTPUT}")
    print(f"  {ISOLATION_OUTPUT}")


if __name__ == "__main__":
    main()