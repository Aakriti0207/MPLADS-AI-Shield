"""Phase 3: deterministic, project-level ML feature engineering.

This module consumes Phase 2's one-row-per-work-id canonical table. It does
not read raw sources, databases, or the legacy project_risk_scores.csv, and it
does not assign a risk score. Missing measurements remain missing (``NaN``).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ml.config import BACKEND_ROOT


CANONICAL_INPUT_PATH = BACKEND_ROOT / "data" / "processed" / "canonical_projects.csv"
FEATURE_OUTPUT_PATH = BACKEND_ROOT / "data" / "processed" / "ml_features.csv"

# Kept as audit metadata: these signals describe source consistency, not fraud.
DATA_QUALITY_COLUMNS = (
    "any_field_conflict", "state_conflict", "mp_conflict", "constituency_conflict",
    "implementing_agency_conflict", "work_category_conflict", "work_description_conflict",
    "elected_nominated_conflict", "recommended_date_conflict",
    "flag_completion_without_sanction", "flag_expenditure_without_sanction",
    "flag_sanction_without_recommendation", "flag_completion_before_sanction",
    "flag_expenditure_before_recommendation", "flag_recommendation_after_sanction",
)
LIFECYCLE_COLUMNS = (
    "has_recommended_record", "has_sanctioned_record", "has_completed_record",
    "has_expenditure_record", "n_lifecycle_stages_present",
)
AMOUNT_COLUMNS = (
    "recommended_amount", "sanction_amount", "amount_disbursed", "total_expenditure",
    "total_amount_in_progress",
)
PAYMENT_COUNT_COLUMNS = (
    "n_expenditure_transactions", "n_distinct_vendors", "n_payment_success",
    "n_payment_in_progress",
)
DATE_COLUMNS = (
    "recommended_date", "sanction_date", "completion_date", "first_expenditure_date",
    "last_expenditure_date",
)
# High-cardinality MP, constituency, and agency fields are raw context only.
RAW_CATEGORICAL_COLUMNS = (
    "houses", "state", "mp", "constituency", "implementing_agency", "elected_nominated",
    "work_category", "work_status", "stages_present",
)
ENCODED_CATEGORICAL_COLUMNS = (
    "houses", "state", "elected_nominated", "work_category", "work_status", "stages_present",
)
REQUIRED_SOURCE_COLUMNS = frozenset(
    ("work_id",) + AMOUNT_COLUMNS + PAYMENT_COUNT_COLUMNS + DATE_COLUMNS
    + LIFECYCLE_COLUMNS + DATA_QUALITY_COLUMNS + RAW_CATEGORICAL_COLUMNS
)
FORBIDDEN_RISK_MARKERS = ("risk_score", "risk_level", "risk_reason", "anomaly_score")
FORBIDDEN_OUTPUT_COLUMNS = frozenset((
    "financial_risk_score", "payment_risk_score", "execution_risk_score",
    "peer_anomaly_score", "isolation_forest_score", "duplicate_risk_score",
))


def _require_columns(canonical_projects: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_SOURCE_COLUMNS - set(canonical_projects.columns))
    if missing:
        raise ValueError("canonical_projects is missing required Phase 2 columns: " + ", ".join(missing))
    if canonical_projects["work_id"].isna().any() or not canonical_projects["work_id"].is_unique:
        raise ValueError("canonical_projects must have a non-null, unique work_id column")


def _numeric(source: pd.DataFrame, column: str) -> pd.Series:
    """Return a numeric copy; malformed values become missing, never zero."""
    return pd.to_numeric(source[column], errors="coerce")


def _indicator(values: pd.Series) -> pd.Series:
    """Normalize canonical boolean values, including CSV-loaded strings."""
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype("int8")
    if pd.api.types.is_numeric_dtype(values):
        return values.fillna(0).ne(0).astype("int8")
    return values.astype("string").str.strip().str.lower().isin(("true", "1", "yes")).astype("int8")


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Divide only where both quantities are known and denominator is nonzero."""
    result = pd.Series(np.nan, index=numerator.index, dtype="float64")
    usable = numerator.notna() & denominator.notna() & denominator.ne(0)
    result.loc[usable] = numerator.loc[usable] / denominator.loc[usable]
    return result.replace([np.inf, -np.inf], np.nan)


def _days_between(start: pd.Series, end: pd.Series) -> pd.Series:
    """Calendar-day interval, preserving missing and negative intervals."""
    return (end - start).dt.days.astype("float64").where(start.notna() & end.notna())


def _category_codes(values: pd.Series) -> pd.Series:
    """Stable, lexicographically ordered codes; missing values are -1."""
    normalized = values.astype("string")
    lookup = {value: code for code, value in enumerate(sorted(normalized.dropna().unique().tolist()))}
    return normalized.map(lookup).fillna(-1).astype("int64")


def build_ml_features(canonical_projects: pd.DataFrame) -> pd.DataFrame:
    """Build Phase 3 features without mutating ``canonical_projects``.

    Ratios with an unknown/zero denominator and durations with a missing
    endpoint are ``NaN``. No labels, thresholds, or risk scores are produced.
    """
    _require_columns(canonical_projects)
    source = canonical_projects.copy(deep=True)
    features = pd.DataFrame({"work_id": source["work_id"].copy()})

    for column in AMOUNT_COLUMNS + PAYMENT_COUNT_COLUMNS:
        features[column] = _numeric(source, column)
    for column in LIFECYCLE_COLUMNS:
        features[column] = _indicator(source[column]) if column.startswith("has_") else _numeric(source, column)
    # Reuse the validated Phase 2 logic rather than recreating these flags.
    for column in DATA_QUALITY_COLUMNS:
        features[column] = _indicator(source[column])
    for column in RAW_CATEGORICAL_COLUMNS:
        features[column] = source[column].astype("string")
    for column in ENCODED_CATEGORICAL_COLUMNS:
        features[f"{column}_category_code"] = _category_codes(source[column])

    dates = {column: pd.to_datetime(source[column], errors="coerce") for column in DATE_COLUMNS}
    for column, values in dates.items():
        features[f"is_{column}_available"] = values.notna().astype("int8")

    recommended, sanctioned = features["recommended_amount"], features["sanction_amount"]
    disbursed, expenditure = features["amount_disbursed"], features["total_expenditure"]
    in_progress = features["total_amount_in_progress"]
    transactions, vendors = features["n_expenditure_transactions"], features["n_distinct_vendors"]
    successes, pending = features["n_payment_success"], features["n_payment_in_progress"]

    features["sanction_vs_recommended_ratio"] = _safe_ratio(sanctioned, recommended)
    features["sanction_minus_recommended_amount"] = sanctioned - recommended
    features["disbursed_to_sanction_ratio"] = _safe_ratio(disbursed, sanctioned)
    features["expenditure_to_sanction_ratio"] = _safe_ratio(expenditure, sanctioned)
    features["in_progress_amount_to_sanction_ratio"] = _safe_ratio(in_progress, sanctioned)
    features["recorded_payment_amount_to_sanction_ratio"] = _safe_ratio(expenditure + in_progress, sanctioned)
    features["payment_success_ratio"] = _safe_ratio(successes, transactions)
    features["payment_in_progress_ratio"] = _safe_ratio(pending, transactions)
    features["transactions_per_vendor"] = _safe_ratio(transactions, vendors)
    features["average_successful_payment_amount"] = _safe_ratio(expenditure, successes)
    features["average_in_progress_payment_amount"] = _safe_ratio(in_progress, pending)

    features["recommendation_to_sanction_days"] = _days_between(dates["recommended_date"], dates["sanction_date"])
    features["sanction_to_completion_days"] = _days_between(dates["sanction_date"], dates["completion_date"])
    features["recommendation_to_completion_days"] = _days_between(dates["recommended_date"], dates["completion_date"])
    features["recommendation_to_first_expenditure_days"] = _days_between(dates["recommended_date"], dates["first_expenditure_date"])
    features["sanction_to_first_expenditure_days"] = _days_between(dates["sanction_date"], dates["first_expenditure_date"])
    features["expenditure_span_days"] = _days_between(dates["first_expenditure_date"], dates["last_expenditure_date"])
    features["lifecycle_stage_coverage_ratio"] = features["n_lifecycle_stages_present"] / 4.0

    if features.columns.duplicated().any():
        raise RuntimeError("Feature construction produced duplicate column names")
    if np.isinf(features.select_dtypes(include=[np.number]).to_numpy(dtype=float)).any():
        raise RuntimeError("Feature construction produced infinite numeric values")
    if (any(marker in column.lower() for column in features.columns for marker in FORBIDDEN_RISK_MARKERS)
            or FORBIDDEN_OUTPUT_COLUMNS.intersection(features.columns)):
        raise RuntimeError("Phase 3 feature output must not contain risk-score columns")
    return features


def build_features_from_canonical_file(path: Path | str = CANONICAL_INPUT_PATH) -> pd.DataFrame:
    """Load a Phase 2 CSV and return reproducible Phase 3 features."""
    return build_ml_features(pd.read_csv(path))


def write_ml_features(features: pd.DataFrame, output_path: Path | str = FEATURE_OUTPUT_PATH) -> Path:
    """Write generated features to the supplied processed-data path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(output_path, index=False)
    return output_path


def main() -> None:
    features = build_features_from_canonical_file()
    output_path = write_ml_features(features)
    print(f"Phase 3 features written: {len(features):,} rows x {len(features.columns)} columns")
    print(output_path)


if __name__ == "__main__":
    main()
