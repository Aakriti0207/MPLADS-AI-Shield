"""Execution and output generation for Phase 5 anomaly analysis."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.anomalies.financial import FINANCIAL_METRICS
from ml.anomalies.statistics import build_baseline, build_peer_index, choose_peer_indices, evaluate_value
from ml.anomalies.timeline import TIMELINE_METRICS
from ml.config import BACKEND_ROOT


FEATURE_INPUT_PATH = BACKEND_ROOT / "data" / "processed" / "ml_features.csv"
OUTPUT_DIR = BACKEND_ROOT / "data" / "processed"
ANOMALY_COLUMNS = [
    "work_id", "metric_name", "domain", "status", "observed_value", "transformed_value",
    "peer_group_level", "peer_group_key", "peer_group_size", "peer_median", "peer_mad",
    "peer_q1", "peer_q3", "modified_z_score", "lower_bound", "upper_bound", "direction",
    "decision_method", "evidence_json",
]
SUMMARY_COLUMNS = [
    "work_id", "financial_metrics_evaluated", "financial_anomaly_count",
    "timeline_metrics_evaluated", "timeline_anomaly_count", "total_anomaly_count",
    "financial_not_evaluable_count", "timeline_not_evaluable_count", "phase5_status",
]
FINANCIAL_COLUMNS = ANOMALY_COLUMNS
TIMELINE_COLUMNS = ANOMALY_COLUMNS
REQUIRED_COLUMNS = frozenset({"work_id", "state", "work_category", *FINANCIAL_METRICS, *TIMELINE_METRICS})


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _valid_for_metric(values: pd.Series, metric_name: str) -> pd.Series:
    valid = _numeric(values).notna() & np.isfinite(_numeric(values))
    if metric_name in {
        "recommended_amount", "sanction_amount", "amount_disbursed",
        "total_expenditure", "total_amount_in_progress",
    }:
        valid &= _numeric(values) >= 0
    if metric_name in TIMELINE_METRICS:
        valid &= _numeric(values) >= 0
    return valid


def _evaluate_metric(frame: pd.DataFrame, metric_name: str, domain: str) -> list[dict]:
    values = _numeric(frame[metric_name]).to_numpy(dtype=float)
    valid_mask = _valid_for_metric(frame[metric_name], metric_name).to_numpy()
    peer_index = build_peer_index(frame, valid_mask)
    rows = []
    for index, row in frame.iterrows():
        observed = values[index]
        if metric_name in TIMELINE_METRICS and np.isfinite(observed) and observed < 0:
            result = {"status": "NOT_EVALUABLE", "direction": "NONE", "modified_z_score": None, "lower_bound": None, "upper_bound": None, "decision_method": "not_evaluable"}
            evidence_reason = "negative_duration_delegated_to_phase4"
            baseline = None
        else:
            level, key, peer_indices = choose_peer_indices(index, peer_index)
            if level is None or not valid_mask[index]:
                result = {"status": "NOT_EVALUABLE", "direction": "NONE", "modified_z_score": None, "lower_bound": None, "upper_bound": None, "decision_method": "not_evaluable"}
                evidence_reason = "missing_observed_value" if not valid_mask[index] else "insufficient_peer_group"
                baseline = None
            else:
                baseline = build_baseline(values[peer_indices], metric_name, level, key, len(peer_indices))
                result = evaluate_value(float(observed), baseline)
                evidence_reason = None
        transformed = None if not np.isfinite(observed) else (float(np.log1p(observed)) if baseline and baseline.transformation == "log1p" else float(observed))
        evidence = {
            "metric_name": metric_name, "observed_value": None if not np.isfinite(observed) else float(observed),
            "decision_method": result["decision_method"], "threshold": 3.5,
        }
        if evidence_reason:
            evidence["reason"] = evidence_reason
        if baseline:
            evidence.update({"peer_group_level": baseline.level, "peer_group_key": baseline.key, "peer_group_size": baseline.size, "peer_median": baseline.median, "peer_mad": baseline.mad, "peer_q1": baseline.q1, "peer_q3": baseline.q3, "transformation": baseline.transformation})
        rows.append({
            "work_id": str(row["work_id"]), "metric_name": metric_name, "domain": domain,
            "status": result["status"], "observed_value": None if not np.isfinite(observed) else float(observed),
            "transformed_value": transformed, "peer_group_level": baseline.level if baseline else None,
            "peer_group_key": baseline.key if baseline else None, "peer_group_size": baseline.size if baseline else 0,
            "peer_median": baseline.median if baseline else None, "peer_mad": baseline.mad if baseline else None,
            "peer_q1": baseline.q1 if baseline else None, "peer_q3": baseline.q3 if baseline else None,
            "modified_z_score": result["modified_z_score"], "lower_bound": result["lower_bound"], "upper_bound": result["upper_bound"],
            "direction": result["direction"], "decision_method": result["decision_method"],
            "evidence_json": json.dumps(evidence, sort_keys=True, allow_nan=False),
        })
    return rows


def _validate_features(features: pd.DataFrame) -> None:
    missing = sorted(REQUIRED_COLUMNS - set(features.columns))
    if missing:
        raise ValueError("Phase 3 features are missing required Phase 5 columns: " + ", ".join(missing))
    if features["work_id"].isna().any() or not features["work_id"].is_unique:
        raise ValueError("Phase 3 features must have a non-null, unique work_id column")


def build_phase5_summary(anomalies: pd.DataFrame) -> pd.DataFrame:
    """Aggregate anomaly rows without slicing the frame once per work ID."""
    evaluated = anomalies["status"].isin(["NORMAL", "ANOMALY"])
    anomalous = anomalies["status"].eq("ANOMALY")
    financial = anomalies["domain"].eq("FINANCIAL")
    timeline = anomalies["domain"].eq("TIMELINE")

    indicators = pd.DataFrame({
        "work_id": anomalies["work_id"].to_numpy(copy=False),
        "financial_metrics_evaluated": (financial & evaluated).astype("int64").to_numpy(),
        "financial_anomaly_count": (financial & anomalous).astype("int64").to_numpy(),
        "timeline_metrics_evaluated": (timeline & evaluated).astype("int64").to_numpy(),
        "timeline_anomaly_count": (timeline & anomalous).astype("int64").to_numpy(),
        "total_anomaly_count": anomalous.astype("int64").to_numpy(),
        "financial_not_evaluable_count": (financial & anomalies["status"].eq("NOT_EVALUABLE")).astype("int64").to_numpy(),
        "timeline_not_evaluable_count": (timeline & anomalies["status"].eq("NOT_EVALUABLE")).astype("int64").to_numpy(),
    })
    summary = indicators.groupby("work_id", sort=False, as_index=False).sum()
    evaluated_count = summary["financial_metrics_evaluated"] + summary["timeline_metrics_evaluated"]
    summary["phase5_status"] = np.select(
        [summary["total_anomaly_count"].gt(0), evaluated_count.gt(0)],
        ["ANOMALY_FOUND", "NO_ANOMALY_FOUND"],
        default="NOT_EVALUABLE",
    )
    return summary[SUMMARY_COLUMNS]


def build_phase5_outputs(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    _validate_features(features)
    source = features.copy(deep=True).reset_index(drop=True)
    financial = [_evaluate_metric(source, metric_name, "FINANCIAL") for metric_name in FINANCIAL_METRICS]
    timeline = [_evaluate_metric(source, metric_name, "TIMELINE") for metric_name in TIMELINE_METRICS]
    financial_rows = [item for group in financial for item in group]
    timeline_rows = [item for group in timeline for item in group]
    anomaly_rows = financial_rows + timeline_rows
    anomalies = pd.DataFrame(anomaly_rows, columns=ANOMALY_COLUMNS)
    return anomalies, build_phase5_summary(anomalies)


def run_phase5_from_file(path: Path | str = FEATURE_INPUT_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    return build_phase5_outputs(pd.read_csv(path))


def write_phase5_outputs(anomalies: pd.DataFrame, summary: pd.DataFrame, output_dir: Path | str = OUTPUT_DIR) -> tuple[Path, Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    financial_path = output_dir / "financial_anomalies.csv"
    timeline_path = output_dir / "timeline_anomalies.csv"
    summary_path = output_dir / "phase5_anomaly_summary.csv"
    anomalies[anomalies.domain == "FINANCIAL"].to_csv(financial_path, index=False)
    anomalies[anomalies.domain == "TIMELINE"].to_csv(timeline_path, index=False)
    summary.to_csv(summary_path, index=False)
    return financial_path, timeline_path, summary_path