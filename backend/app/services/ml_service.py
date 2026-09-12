"""Read-only application integration for the current Phase 9 output.

The ML package remains the owner of feature, detector, and fusion logic.
This module only loads the existing processed inputs, runs the existing
Risk Fusion contract once per process, and converts one output row into an
API-safe structure. It never reads the legacy Phase 2 score CSV or writes
processed artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any, Iterable

import pandas as pd

from ml.config import BACKEND_ROOT
from ml.risk import build_output, load_inputs, validate_inputs


PROCESSED_DIR = BACKEND_ROOT / "data" / "processed"

_cache_lock = Lock()
_cached_inputs: dict[str, pd.DataFrame] | None = None


def _load_current_inputs() -> dict[str, pd.DataFrame]:
    """Load and validate immutable Phase 4-8 artifacts once per process."""
    inputs = load_inputs(PROCESSED_DIR)
    validate_inputs(inputs)
    return inputs


def _current_inputs() -> dict[str, pd.DataFrame]:
    global _cached_inputs
    if _cached_inputs is None:
        with _cache_lock:
            if _cached_inputs is None:
                _cached_inputs = _load_current_inputs()
    return _cached_inputs


def clear_cache() -> None:
    """Clear the in-process snapshot, primarily for tests and deployments."""
    global _cached_inputs
    with _cache_lock:
        _cached_inputs = None


def _inputs_for_work_id(work_id: str) -> dict[str, pd.DataFrame] | None:
    """Create the smallest valid Risk Fusion input contract for one work."""
    source = _current_inputs()
    canonical = source["canonical"]
    canonical_mask = canonical["work_id"].astype(str).eq(work_id)
    if not canonical_mask.any():
        return None

    scoped: dict[str, pd.DataFrame] = {}
    for name, frame in source.items():
        if name == "duplicate_matches":
            mask = frame["work_id_a"].astype(str).eq(work_id) | frame["work_id_b"].astype(str).eq(work_id)
        else:
            mask = frame["work_id"].astype(str).eq(work_id)
        scoped[name] = frame.loc[mask].copy(deep=True)
    return scoped


def _json_object(raw: Any, default: dict[str, Any]) -> dict[str, Any]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return default.copy()
    try:
        value = json.loads(str(raw)) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return default.copy()
    return value if isinstance(value, dict) else default.copy()


def _json_list(raw: Any) -> list[str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    try:
        value = json.loads(str(raw)) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return []
    return [str(item) for item in value] if isinstance(value, list) else []


def _nullable_string(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value)


def _result_from_row(row: pd.Series) -> dict[str, Any]:
    decimal_fields = (
        "risk_score", "compliance_contribution", "financial_anomaly_contribution",
        "timeline_anomaly_contribution", "duplicate_contribution",
        "data_quality_contribution", "payment_contribution",
        "isolation_forest_contribution",
    )
    integer_fields = (
        "total_evidence_signals", "high_severity_signal_count",
        "medium_severity_signal_count", "low_severity_signal_count",
    )
    boolean_fields = (
        "has_compliance_signal", "has_financial_anomaly", "has_timeline_anomaly",
        "has_duplicate_signal", "has_data_quality_signal", "has_payment_signal",
        "has_isolation_forest_signal",
    )
    result: dict[str, Any] = {"work_id": str(row["work_id"])}
    result.update({field: float(row[field]) for field in decimal_fields})
    result.update({field: int(row[field]) for field in integer_fields})
    result.update({field: bool(row[field]) for field in boolean_fields})
    result["risk_level"] = str(row["risk_level"])
    result["evidence_status"] = str(row["evidence_status"])
    for field in ("top_reason_1", "top_reason_2", "top_reason_3"):
        result[field] = _nullable_string(row[field])
    result["risk_reasons"] = _json_list(row["risk_reasons"])
    result["source_signal_summary"] = _json_object(row["source_signal_summary"], {"signals": []})
    return result


def get_risk_fusion_result(work_id: str) -> dict[str, Any] | None:
    """Return one current Phase 9 result, or ``None`` if it is unavailable."""
    inputs = _inputs_for_work_id(work_id)
    if inputs is None:
        return None
    output = build_output(inputs)
    return _result_from_row(output.iloc[0])


def get_risk_fusion_results(work_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    """Return current results for a bounded set of project IDs."""
    requested = {str(work_id) for work_id in work_ids}
    if not requested:
        return {}
    results = {}
    for work_id in requested:
        result = get_risk_fusion_result(work_id)
        if result is not None:
            results[work_id] = result
    return results