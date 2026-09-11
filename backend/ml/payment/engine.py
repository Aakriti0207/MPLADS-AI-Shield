"""Unsupervised, explainable Payment AI for project-level data.

The model learns robust distributions from historical rows and can score a
separate, unseen dataframe. It does not use Work ID, labels, or future risk
outputs. Missing and invalid payment evidence is reported explicitly rather
than converted into suspiciousness.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


PAYMENT_OUTPUT_COLUMNS = [
    "work_id", "payment_status", "payment_risk_score", "payment_anomaly_status",
    "payment_signal_count", "payment_high_signal_count", "payment_reasons",
    "payment_evidence",
]
PAYMENT_SIGNAL_COLUMNS = (
    "payment_utilization_ratio", "payment_progress_ratio", "payment_transaction_count",
    "payment_transactions_per_vendor", "payment_success_ratio", "payment_in_progress_ratio",
    "payment_expenditure_span_days",
)
RAW_PAYMENT_COLUMNS = (
    "sanction_amount", "total_expenditure", "total_amount_in_progress",
    "n_expenditure_transactions", "n_distinct_vendors", "n_payment_success",
    "n_payment_in_progress",
)
OPTIONAL_RAW_PAYMENT_COLUMNS = ("amount_disbursed", "expenditure_span_days")
OPTIONAL_DERIVED_PAYMENT_COLUMNS = (
    "recorded_payment_amount_to_sanction_ratio", "expenditure_to_sanction_ratio",
    "payment_success_ratio", "payment_in_progress_ratio",
)
PAYMENT_FAMILIES = {
    "payment_utilization_ratio": "utilization_expenditure",
    "payment_progress_ratio": "completion_progress",
    "payment_transaction_count": "transaction_activity",
    "payment_expenditure_span_days": "transaction_activity",
    "payment_transactions_per_vendor": "vendor_concentration",
    "payment_success_ratio": "completion_progress",
    "payment_in_progress_ratio": "completion_progress",
}
MIN_TRAINING_VALUES = 8
ANOMALY_Z_THRESHOLD = 3.5
HIGH_Z_THRESHOLD = 5.0
MAX_SCORE = 100.0


@dataclass(frozen=True)
class SignalBaseline:
    median: float
    mad: float
    q1: float
    q3: float
    transformation: str
    count: int
    stability: str


@dataclass(frozen=True)
class BaselineDiagnostics:
    count: int
    status: str


@dataclass(frozen=True)
class PaymentConfig:
    """Configurable, data-independent policy for robust payment scoring."""

    anomaly_z_threshold: float = ANOMALY_Z_THRESHOLD
    high_z_threshold: float = HIGH_Z_THRESHOLD
    max_score: float = MAX_SCORE
    min_training_values: int = MIN_TRAINING_VALUES
    min_training_families: int = 2
    family_caps: tuple[tuple[str, float], ...] = (
        ("utilization_expenditure", 25.0),
        ("completion_progress", 25.0),
        ("transaction_activity", 25.0),
        ("vendor_concentration", 25.0),
    )

    def __post_init__(self) -> None:
        if self.anomaly_z_threshold <= 0 or self.high_z_threshold < self.anomaly_z_threshold:
            raise ValueError("high_z_threshold must be >= a positive anomaly_z_threshold")
        if self.max_score <= 0 or self.min_training_values < 3 or self.min_training_families < 2:
            raise ValueError("max_score must be positive, min_training_values at least 3, and min_training_families at least 2")
        caps = dict(self.family_caps)
        if set(caps) != set(PAYMENT_FAMILIES.values()) or any(value <= 0 for value in caps.values()):
            raise ValueError("family_caps must provide positive caps for every payment evidence family")


@dataclass(frozen=True)
class PaymentModel:
    """Fitted historical baselines; independent of the rows being scored."""

    baselines: dict[str, SignalBaseline]
    feature_columns: tuple[str, ...]
    config: PaymentConfig = PaymentConfig()
    baseline_diagnostics: dict[str, BaselineDiagnostics] = field(default_factory=dict)


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(np.nan, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    result = pd.Series(np.nan, index=numerator.index, dtype="float64")
    usable = numerator.notna() & denominator.notna() & denominator.gt(0)
    result.loc[usable] = numerator.loc[usable] / denominator.loc[usable]
    return result.replace([np.inf, -np.inf], np.nan)


def _validate_input_schema(frame: pd.DataFrame) -> None:
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("payment input must be a pandas DataFrame")
    missing = sorted(set(("work_id",) + RAW_PAYMENT_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError("payment input is missing required columns: " + ", ".join(missing))
    if frame["work_id"].isna().any() or not frame["work_id"].is_unique:
        raise ValueError("work_id must be non-null and unique")


def _validated_raw_values(frame: pd.DataFrame) -> dict[str, pd.Series]:
    values = {column: _numeric(frame, column) for column in RAW_PAYMENT_COLUMNS + OPTIONAL_RAW_PAYMENT_COLUMNS}
    for series in values.values():
        series.loc[series.lt(0)] = np.nan

    transactions = values["n_expenditure_transactions"]
    successes = values["n_payment_success"]
    pending = values["n_payment_in_progress"]
    complete_counts = transactions.notna() & successes.notna() & pending.notna()
    inconsistent_counts = complete_counts & (
        successes.gt(transactions) | successes.add(pending).gt(transactions)
    )
    values["n_payment_success"] = successes.mask(inconsistent_counts)
    values["n_payment_in_progress"] = pending.mask(inconsistent_counts)
    values["n_distinct_vendors"] = values["n_distinct_vendors"].mask(
        transactions.notna() & values["n_distinct_vendors"].notna()
        & values["n_distinct_vendors"].gt(transactions)
    )
    return values


def build_payment_signals(frame: pd.DataFrame) -> pd.DataFrame:
    """Derive supported payment signals without mutating ``frame``.

    Negative monetary/count values are invalid and become missing. A zero
    sanctioned amount makes ratios not evaluable, but does not make the row
    anomalous by itself.
    """
    source = frame.copy(deep=True).reset_index(drop=True)
    values = _validated_raw_values(source)
    sanction = values["sanction_amount"]
    expenditure = values["total_expenditure"]
    in_progress = values["total_amount_in_progress"]
    transactions = values["n_expenditure_transactions"]
    vendors = values["n_distinct_vendors"]
    successes = values["n_payment_success"]
    pending = values["n_payment_in_progress"]

    recorded = expenditure + in_progress
    signals = pd.DataFrame(index=source.index)
    utilization = _safe_ratio(recorded, sanction)
    signals["payment_utilization_ratio"] = utilization.mask(utilization.gt(1))
    signals["payment_progress_ratio"] = _safe_ratio(expenditure, recorded)
    signals["payment_transaction_count"] = transactions
    signals["payment_transactions_per_vendor"] = _safe_ratio(transactions, vendors)
    signals["payment_success_ratio"] = _safe_ratio(successes, transactions)
    signals["payment_in_progress_ratio"] = _safe_ratio(pending, transactions)
    signals["payment_expenditure_span_days"] = values["expenditure_span_days"]
    signals.loc[signals["payment_expenditure_span_days"].lt(0), "payment_expenditure_span_days"] = np.nan
    return signals[list(PAYMENT_SIGNAL_COLUMNS)]


def _payment_evidence_mask(frame: pd.DataFrame) -> pd.Series:
    """Identify rows with observed payment activity, not merely a sanction."""
    source = frame.copy(deep=True).reset_index(drop=True)
    activity_columns = (
        "amount_disbursed", "total_expenditure", "total_amount_in_progress",
        "n_expenditure_transactions", "n_payment_success", "n_payment_in_progress",
    )
    values = _validated_raw_values(source)
    activity = pd.DataFrame({column: values.get(column, _numeric(source, column)) for column in activity_columns}, index=source.index)
    return activity.gt(0).any(axis=1)


def _transformation(signal: str, values: np.ndarray) -> str:
    if signal in {"payment_transaction_count", "payment_transactions_per_vendor", "payment_expenditure_span_days"} and np.all(values >= 0):
        return "log1p"
    return "none"


def _transform(values: np.ndarray, transformation: str) -> np.ndarray:
    return np.log1p(values) if transformation == "log1p" else values


def fit_payment_model(
    frame: pd.DataFrame,
    min_training_values: int = MIN_TRAINING_VALUES,
    config: PaymentConfig | None = None,
) -> PaymentModel:
    """Fit robust, label-free baselines on historical payment signals."""
    if config is None:
        config = PaymentConfig(min_training_values=min_training_values)
    elif min_training_values != MIN_TRAINING_VALUES and min_training_values != config.min_training_values:
        raise ValueError("set min_training_values on PaymentConfig or use the default argument")
    _validate_input_schema(frame)
    normalized = frame.copy(deep=True).reset_index(drop=True)
    signals = build_payment_signals(normalized)
    evidence_mask = _payment_evidence_mask(normalized)
    baselines: dict[str, SignalBaseline] = {}
    diagnostics: dict[str, BaselineDiagnostics] = {}
    for signal in PAYMENT_SIGNAL_COLUMNS:
        values = pd.to_numeric(signals[signal], errors="coerce").to_numpy(dtype=float)
        values = values[evidence_mask.to_numpy()]
        values = values[np.isfinite(values)]
        if len(values) < config.min_training_values:
            diagnostics[signal] = BaselineDiagnostics(len(values), "INSUFFICIENT_SAMPLE")
            continue
        transformation = _transformation(signal, values)
        transformed = _transform(values, transformation)
        median = float(np.median(transformed))
        mad = float(np.median(np.abs(transformed - median)))
        q1, q3 = np.percentile(transformed, [25, 75])
        if mad > 0:
            stability = "MAD"
            status = "FITTED"
        elif q3 > q1:
            stability = "IQR_FALLBACK"
            status = "FITTED_IQR_FALLBACK"
        else:
            stability = "UNSTABLE_ZERO_VARIATION"
            status = "UNSTABLE"
        diagnostics[signal] = BaselineDiagnostics(len(values), status)
        if status != "UNSTABLE":
            baselines[signal] = SignalBaseline(median, mad, float(q1), float(q3), transformation, len(values), stability)
    fitted_families = {PAYMENT_FAMILIES[signal] for signal in baselines}
    if len(fitted_families) < config.min_training_families:
        raise ValueError("Insufficient stable payment signal families to fit a model")
    return PaymentModel(baselines, tuple(baselines), config, diagnostics)


def _evaluate(value: float, baseline: SignalBaseline, config: PaymentConfig) -> tuple[str, float, str]:
    transformed = float(_transform(np.asarray([value]), baseline.transformation)[0])
    if baseline.mad > 0:
        robust_z = abs(0.6745 * (transformed - baseline.median) / baseline.mad)
        if robust_z >= config.anomaly_z_threshold:
            return ("HIGH" if robust_z >= config.high_z_threshold else "MEDIUM", robust_z, "modified_z_score")
        return "NORMAL", robust_z, "modified_z_score"
    iqr = baseline.q3 - baseline.q1
    if iqr <= 0:
        return "NORMAL", 0.0, "not_anomalous"
    distance = max((baseline.q1 - transformed) / (1.5 * iqr), (transformed - baseline.q3) / (1.5 * iqr), 0.0)
    return ("MEDIUM", float(config.anomaly_z_threshold + distance), "iqr_fallback") if distance > 0 else ("NORMAL", 0.0, "iqr_fallback")


def score_payment_data(model: PaymentModel, frame: pd.DataFrame) -> pd.DataFrame:
    """Score historical or unseen rows using a previously fitted model."""
    if not isinstance(model, PaymentModel):
        raise TypeError("model must be a PaymentModel returned by fit_payment_model")
    _validate_input_schema(frame)
    normalized = frame.copy(deep=True).reset_index(drop=True)
    signals = build_payment_signals(normalized)
    evidence_mask = _payment_evidence_mask(normalized)
    family_caps = dict(model.config.family_caps)
    rows = []
    for index, row in signals.iterrows():
        available = {name: float(row[name]) for name in PAYMENT_SIGNAL_COLUMNS if pd.notna(row[name]) and np.isfinite(row[name])}
        fitted = {name: value for name, value in available.items() if name in model.baselines}
        if not evidence_mask.iloc[index] or not fitted:
            reason = "no_valid_payment_activity" if not evidence_mask.iloc[index] else "no_fitted_baseline_for_available_signals"
            rows.append({"work_id": str(normalized.iloc[index]["work_id"]), "payment_status": "NOT_EVALUABLE", "payment_risk_score": 0.0, "payment_anomaly_status": "NOT_EVALUABLE", "payment_signal_count": 0, "payment_high_signal_count": 0, "payment_reasons": "[]", "payment_evidence": json.dumps({"reason": reason, "available_signals": sorted(available)}, sort_keys=True)})
            continue
        evidence = []
        for signal, value in fitted.items():
            baseline = model.baselines[signal]
            status, severity_value, method = _evaluate(value, baseline, model.config)
            if status != "NORMAL":
                evidence.append({"signal": signal, "family": PAYMENT_FAMILIES[signal], "value": round(value, 6), "severity": status, "strength": round(severity_value, 4), "method": method})
        evidence.sort(key=lambda item: (-item["strength"], item["signal"]))
        family_scores = {family: min(family_caps[family], sum(12.0 if item["severity"] == "HIGH" else 7.0 for item in evidence if item["family"] == family)) for family in family_caps}
        score = min(model.config.max_score, sum(family_scores.values()))
        status = "ANOMALY" if evidence else "NORMAL"
        reasons = [f"{item['family']} signal {item['signal']} is unusually {('high' if item['value'] >= model.baselines[item['signal']].median else 'low')} relative to fitted historical payment behavior (" + item["method"] + ")." for item in evidence]
        rows.append({"work_id": str(normalized.iloc[index]["work_id"]), "payment_status": "EVALUABLE", "payment_risk_score": round(score, 2), "payment_anomaly_status": status, "payment_signal_count": len(evidence), "payment_high_signal_count": sum(item["severity"] == "HIGH" for item in evidence), "payment_reasons": json.dumps(reasons, ensure_ascii=False), "payment_evidence": json.dumps({"signals": evidence, "family_contributions": family_scores}, sort_keys=True)})
    result = pd.DataFrame(rows, columns=PAYMENT_OUTPUT_COLUMNS)
    if result["payment_risk_score"].isna().any() or not result["payment_risk_score"].between(0, model.config.max_score).all():
        raise RuntimeError("Payment AI produced an invalid bounded score")
    return result


def write_payment_outputs(output: pd.DataFrame, output_path: str) -> str:
    """Write only the caller-selected Payment AI output path."""
    if list(output.columns) != PAYMENT_OUTPUT_COLUMNS:
        raise ValueError("Payment output schema does not match PAYMENT_OUTPUT_COLUMNS")
    output.to_csv(output_path, index=False)
    return output_path