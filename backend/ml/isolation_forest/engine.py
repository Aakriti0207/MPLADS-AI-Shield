"""Independent Phase 8 multivariate Isolation Forest detector.

The detector consumes project-level feature DataFrames only. It does not load
the current CSV fixture, use labels, or consume outputs from another AI
component.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline


ISOLATION_FOREST_FEATURES = (
    "sanction_amount", "recommended_amount", "amount_disbursed",
    "disbursed_to_sanction_ratio", "sanction_vs_recommended_ratio",
    "recommendation_to_sanction_days", "sanction_to_completion_days",
    "recommendation_to_completion_days", "expenditure_span_days",
    "n_lifecycle_stages_present", "has_recommended_record",
    "has_sanctioned_record", "has_completed_record", "has_expenditure_record",
    "n_expenditure_transactions", "n_distinct_vendors", "payment_success_ratio",
)
ISOLATION_FOREST_OUTPUT_COLUMNS = [
    "work_id", "isolation_forest_risk_score", "isolation_forest_status",
    "isolation_forest_raw_score", "isolation_forest_percentile",
    "isolation_forest_reasons", "isolation_forest_evidence",
]
MAX_SCORE = 100.0


@dataclass(frozen=True)
class IsolationForestConfig:
    """Data-independent policy for fitting and interpreting the detector."""

    random_state: int = 42
    n_estimators: int = 200
    contamination: str | float = "auto"
    min_training_rows: int = 20
    min_selected_features: int = 2
    min_valid_values_per_feature: int = 5
    min_observed_features_per_row: int = 1
    sparse_missingness_threshold: float = 0.20
    anomaly_score_threshold: float = 75.0
    max_samples: str | int = "auto"

    def __post_init__(self) -> None:
        if self.random_state is None or self.n_estimators < 10:
            raise ValueError("random_state is required and n_estimators must be at least 10")
        if self.min_training_rows < 3 or self.min_selected_features < 1:
            raise ValueError("minimum training rows must be at least 3 and feature count must be positive")
        if self.min_valid_values_per_feature < 2 or self.min_observed_features_per_row < 1:
            raise ValueError("minimum valid values and observed features must be positive")
        if not 0.0 <= self.sparse_missingness_threshold <= 1.0:
            raise ValueError("sparse_missingness_threshold must be between 0 and 1")
        if not 0.0 < self.anomaly_score_threshold <= MAX_SCORE:
            raise ValueError("anomaly_score_threshold must be between 0 and 100")


@dataclass
class IsolationForestModel:
    """Fitted model and all training-only state needed for inference."""

    estimator: IsolationForest
    preprocessing: Pipeline
    config: IsolationForestConfig
    selected_features: tuple[str, ...]
    missing_supported_features: tuple[str, ...]
    model_features: tuple[str, ...]
    training_row_count: int
    training_raw_scores: np.ndarray
    training_raw_min: float
    training_raw_max: float
    preprocessing_metadata: dict[str, Any] = field(default_factory=dict)
    feature_diagnostics: dict[str, dict[str, Any]] = field(default_factory=dict)


def _validate_frame(frame: pd.DataFrame, label: str) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{label} must be a pandas DataFrame")
    if "work_id" not in frame.columns:
        raise ValueError(f"{label} is missing required column: work_id")
    if frame["work_id"].isna().any() or not frame["work_id"].is_unique:
        raise ValueError(f"{label} work_id values must be non-null and unique")


def _numeric_features(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame({column: pd.to_numeric(frame[column], errors="coerce") for column in columns}, index=frame.index)


def _feature_frame(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    values = pd.DataFrame(index=frame.index)
    for column in columns:
        values[column] = pd.to_numeric(frame[column], errors="coerce") if column in frame else np.nan
    return values


def _row_observed(values: pd.DataFrame, min_observed: int) -> pd.Series:
    return values.notna().sum(axis=1).ge(min_observed)


def _score_to_risk(raw_scores: np.ndarray, minimum: float, maximum: float) -> np.ndarray:
    if maximum <= minimum:
        return np.full(len(raw_scores), 50.0, dtype=float)
    return np.clip((maximum - raw_scores) / (maximum - minimum) * MAX_SCORE, 0.0, MAX_SCORE)


def _percentile(raw_scores: np.ndarray, training_scores: np.ndarray) -> np.ndarray:
    ordered = np.sort(training_scores)
    return np.searchsorted(ordered, raw_scores, side="right") / len(ordered) * 100.0


def _evidence(
    work_id: str,
    values: pd.Series,
    observed: int,
    model: IsolationForestModel,
    raw_score: float | None,
    risk_score: float,
) -> tuple[str, str]:
    missing = [column for column in model.selected_features if pd.isna(values.get(column))]
    payload: dict[str, Any] = {
        "interpretation": "unusual_multivariate_project_feature_combination",
        "work_id": work_id,
        "selected_features": list(model.selected_features),
        "observed_feature_count": observed,
        "missing_selected_features": missing,
        "model_features": list(model.model_features),
        "raw_decision_function": raw_score,
        "risk_score": round(risk_score, 4),
    }
    if raw_score is None:
        payload["reason"] = "insufficient_observed_supported_features"
        return "Project has insufficient observed supported features for Isolation Forest evaluation.", json.dumps(payload, sort_keys=True, allow_nan=False)
    reason = "Project is unusual relative to the fitted multivariate project-feature distribution; this is not a fraud finding."
    if missing:
        reason += " Some supported features were imputed from training medians."
    return reason, json.dumps(payload, sort_keys=True, allow_nan=False)


def fit_isolation_forest_model(
    history: pd.DataFrame,
    config: IsolationForestConfig | None = None,
) -> IsolationForestModel:
    """Fit on historical rows without reading or depending on a file path."""
    config = config or IsolationForestConfig()
    _validate_frame(history, "history")
    if history.empty or len(history) < config.min_training_rows:
        raise ValueError(f"history must contain at least {config.min_training_rows} rows")

    present = tuple(column for column in ISOLATION_FOREST_FEATURES if column in history.columns)
    missing = tuple(column for column in ISOLATION_FOREST_FEATURES if column not in history.columns)
    if not present:
        raise ValueError("history has no supported Isolation Forest feature columns")

    values = _numeric_features(history, present)
    diagnostics: dict[str, dict[str, Any]] = {}
    usable: list[str] = []
    for column in present:
        numeric = values[column]
        valid = numeric.notna() & np.isfinite(numeric)
        diagnostics[column] = {
            "present": True,
            "valid_count": int(valid.sum()),
            "missing_count": int((~valid).sum()),
            "missing_fraction": float((~valid).mean()),
            "distinct_valid_count": int(numeric[valid].nunique()),
            "status": "CANDIDATE",
        }
        if valid.sum() >= config.min_valid_values_per_feature and numeric[valid].nunique() > 1:
            usable.append(column)
        else:
            diagnostics[column]["status"] = "INSUFFICIENT_OR_ZERO_VARIANCE"

    if len(usable) < config.min_selected_features:
        raise ValueError(
            f"history has only {len(usable)} viable supported features; "
            f"at least {config.min_selected_features} are required"
        )

    selected = tuple(usable)
    selected_values = values[list(selected)]
    imputer = SimpleImputer(strategy="median", add_indicator=True)
    preprocessing = Pipeline([("imputer", imputer)])
    transformed = preprocessing.fit_transform(selected_values)
    transformed_names = list(selected) + [
        f"{column}__missing" for column in selected if selected_values[column].isna().any()
    ]
    if transformed.shape[1] != len(transformed_names):
        raise RuntimeError("preprocessing metadata does not match transformed feature matrix")

    estimator = IsolationForest(
        n_estimators=config.n_estimators,
        contamination=config.contamination,
        max_samples=config.max_samples,
        random_state=config.random_state,
    )
    estimator.fit(transformed)
    training_raw = estimator.decision_function(transformed).astype(float)
    raw_min, raw_max = float(training_raw.min()), float(training_raw.max())
    metadata = {
        "imputation_strategy": "median",
        "missing_indicators": [name for name in transformed_names if name.endswith("__missing")],
        "transformed_feature_names": transformed_names,
        "fit_on_training_rows_only": True,
        "training_medians": {column: float(value) for column, value in zip(selected, imputer.statistics_)},
        "training_raw_score_min": raw_min,
        "training_raw_score_max": raw_max,
    }
    for column in selected:
        diagnostics[column]["status"] = "SELECTED"
        diagnostics[column]["sparse_missingness_indicator"] = diagnostics[column]["missing_fraction"] >= config.sparse_missingness_threshold
    return IsolationForestModel(
        estimator=estimator,
        preprocessing=preprocessing,
        config=config,
        selected_features=selected,
        missing_supported_features=missing,
        model_features=tuple(transformed_names),
        training_row_count=len(history),
        training_raw_scores=training_raw.copy(),
        training_raw_min=raw_min,
        training_raw_max=raw_max,
        preprocessing_metadata=metadata,
        feature_diagnostics=diagnostics,
    )


def score_isolation_forest_data(model: IsolationForestModel, new_rows: pd.DataFrame) -> pd.DataFrame:
    """Score unseen rows using the fitted preprocessing and estimator only."""
    if not isinstance(model, IsolationForestModel):
        raise TypeError("model must be an IsolationForestModel returned by fit_isolation_forest_model")
    _validate_frame(new_rows, "new_rows")
    normalized = new_rows.copy(deep=True).reset_index(drop=True)
    if normalized.empty:
        return pd.DataFrame(columns=ISOLATION_FOREST_OUTPUT_COLUMNS)

    values = _feature_frame(normalized, model.selected_features)
    evaluable = _row_observed(values, model.config.min_observed_features_per_row)
    transformed = model.preprocessing.transform(values)
    raw_scores = np.full(len(normalized), np.nan, dtype=float)
    evaluable_mask = evaluable.to_numpy()
    if evaluable_mask.any():
        raw_scores[evaluable_mask] = model.estimator.decision_function(transformed[evaluable_mask])
    risk_scores = np.zeros(len(normalized), dtype=float)
    risk_scores[evaluable.to_numpy()] = _score_to_risk(
        raw_scores[evaluable.to_numpy()], model.training_raw_min, model.training_raw_max
    )
    percentiles = np.full(len(normalized), np.nan, dtype=float)
    percentiles[evaluable.to_numpy()] = _percentile(
        raw_scores[evaluable.to_numpy()], model.training_raw_scores
    )

    rows = []
    for index, work_id in enumerate(normalized["work_id"].astype(str)):
        observed = int(values.iloc[index].notna().sum())
        is_evaluable = bool(evaluable.iloc[index])
        score = float(round(risk_scores[index], 4))
        raw = None if not is_evaluable else float(raw_scores[index])
        percentile = None if not is_evaluable else float(round(percentiles[index], 4))
        status = "NOT_EVALUABLE" if not is_evaluable else ("ANOMALY" if score >= model.config.anomaly_score_threshold else "NORMAL")
        reason, evidence = _evidence(work_id, values.iloc[index], observed, model, raw, score)
        rows.append({
            "work_id": work_id,
            "isolation_forest_risk_score": score,
            "isolation_forest_status": status,
            "isolation_forest_raw_score": raw,
            "isolation_forest_percentile": percentile,
            "isolation_forest_reasons": json.dumps([reason]),
            "isolation_forest_evidence": evidence,
        })
    return pd.DataFrame(rows, columns=ISOLATION_FOREST_OUTPUT_COLUMNS)


def write_isolation_forest_outputs(result: pd.DataFrame, output_path: Path | str) -> Path:
    """Write output only when the caller explicitly supplies a path."""
    if list(result.columns) != ISOLATION_FOREST_OUTPUT_COLUMNS:
        raise ValueError("Isolation Forest output schema does not match ISOLATION_FOREST_OUTPUT_COLUMNS")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    return output_path