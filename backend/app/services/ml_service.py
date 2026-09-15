"""
Read-only application integration for the current Phase 9 output.

The ML package remains the owner of feature, detector, and fusion logic.

This module only:
    1. Loads the existing processed inputs.
    2. Validates the Phase 7 input contract.
    3. Runs the existing Risk Fusion pipeline once per process.
    4. Caches the resulting project-level Risk Fusion output.
    5. Converts requested output rows into API-safe structures.

It never:
    - recomputes individual ML features,
    - changes Risk Fusion weights,
    - reads the legacy Phase 2 risk-score CSV,
    - writes processed artifacts,
    - fabricates missing evidence.

If a required upstream Phase 4/5/6 artifact is missing, the error is
allowed to surface clearly rather than silently producing an incomplete
risk score.
"""

from __future__ import annotations

import json
from threading import Lock
from typing import Any, Iterable

import pandas as pd

from ml.config import BACKEND_ROOT
from ml.risk import build_output, load_inputs, validate_inputs


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROCESSED_DIR = BACKEND_ROOT / "data" / "processed"


# ---------------------------------------------------------------------------
# Process-local caches
# ---------------------------------------------------------------------------

_cache_lock = Lock()

# Validated Phase 4-6/optional inputs.
_cached_inputs: dict[str, pd.DataFrame] | None = None

# Full Phase 9 Risk Fusion output.
_cached_output: pd.DataFrame | None = None


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def _load_current_inputs() -> dict[str, pd.DataFrame]:
    """
    Load and validate the current Phase 7/9 input contract.

    The underlying ML package remains responsible for determining which
    files are required and validating their schemas.
    """

    inputs = load_inputs(PROCESSED_DIR)
    validate_inputs(inputs)

    return inputs


def _current_inputs() -> dict[str, pd.DataFrame]:
    """
    Return the validated process-local input snapshot.

    Inputs are loaded only once per process unless clear_cache() is called.
    """

    global _cached_inputs

    if _cached_inputs is None:
        with _cache_lock:
            if _cached_inputs is None:
                _cached_inputs = _load_current_inputs()

    return _cached_inputs


# ---------------------------------------------------------------------------
# Risk Fusion output
# ---------------------------------------------------------------------------

def _current_output() -> pd.DataFrame:
    """
    Run the complete Risk Fusion pipeline once and cache its output.

    This is intentionally performed against the complete canonical project
    universe rather than creating a one-project subset.

    This preserves the semantics of:
        - peer/context-aware anomaly evidence,
        - duplicate evidence,
        - canonical Work ID coverage,
        - evidence-status calculation,
        - deterministic ranking/reason generation.
    """

    global _cached_output

    if _cached_output is None:
        with _cache_lock:
            if _cached_output is None:
                inputs = _current_inputs()

                output = build_output(inputs)

                if output is None or output.empty:
                    raise RuntimeError(
                        "Risk Fusion produced no output rows."
                    )

                if "work_id" not in output.columns:
                    raise RuntimeError(
                        "Risk Fusion output is missing the work_id column."
                    )

                output = output.copy(deep=True)

                output["work_id"] = output["work_id"].astype(str)

                if output["work_id"].isna().any():
                    raise RuntimeError(
                        "Risk Fusion output contains null work_id values."
                    )

                if not output["work_id"].is_unique:
                    raise RuntimeError(
                        "Risk Fusion output contains duplicate work_id values."
                    )

                _cached_output = output

    return _cached_output


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def clear_cache() -> None:
    """
    Clear the in-process Risk Fusion snapshot.

    This is primarily useful for tests and deployments after the processed
    Phase 4-6 artifacts have been regenerated.
    """

    global _cached_inputs
    global _cached_output

    with _cache_lock:
        _cached_inputs = None
        _cached_output = None


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _json_object(
    raw: Any,
    default: dict[str, Any],
) -> dict[str, Any]:
    """
    Safely parse a JSON object from a processed CSV value.
    """

    if raw is None:
        return default.copy()

    if isinstance(raw, float) and pd.isna(raw):
        return default.copy()

    try:
        value = (
            json.loads(str(raw))
            if isinstance(raw, str)
            else raw
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return default.copy()

    return value if isinstance(value, dict) else default.copy()


def _json_list(raw: Any) -> list[str]:
    """
    Safely parse a JSON list from a processed CSV value.
    """

    if raw is None:
        return []

    if isinstance(raw, float) and pd.isna(raw):
        return []

    try:
        value = (
            json.loads(str(raw))
            if isinstance(raw, str)
            else raw
        )
    except (TypeError, ValueError, json.JSONDecodeError):
        return []

    if not isinstance(value, list):
        return []

    return [str(item) for item in value]


def _nullable_string(value: Any) -> str | None:
    """
    Convert a value to a nullable API-safe string.
    """

    if value is None:
        return None

    if isinstance(value, float) and pd.isna(value):
        return None

    return str(value)


# ---------------------------------------------------------------------------
# API result conversion
# ---------------------------------------------------------------------------

def _result_from_row(row: pd.Series) -> dict[str, Any]:
    """
    Convert one Risk Fusion output row into an API-safe dictionary.
    """

    decimal_fields = (
        "risk_score",
        "compliance_contribution",
        "financial_anomaly_contribution",
        "timeline_anomaly_contribution",
        "duplicate_contribution",
        "data_quality_contribution",
        "payment_contribution",
        "isolation_forest_contribution",
    )

    integer_fields = (
        "total_evidence_signals",
        "high_severity_signal_count",
        "medium_severity_signal_count",
        "low_severity_signal_count",
    )

    boolean_fields = (
        "has_compliance_signal",
        "has_financial_anomaly",
        "has_timeline_anomaly",
        "has_duplicate_signal",
        "has_data_quality_signal",
        "has_payment_signal",
        "has_isolation_forest_signal",
    )

    result: dict[str, Any] = {
        "work_id": str(row["work_id"])
    }

    # -----------------------------------------------------------------------
    # Numeric values
    # -----------------------------------------------------------------------

    for field in decimal_fields:
        value = row[field]

        if pd.isna(value):
            result[field] = 0.0
        else:
            result[field] = float(value)

    for field in integer_fields:
        value = row[field]

        if pd.isna(value):
            result[field] = 0
        else:
            result[field] = int(value)

    # -----------------------------------------------------------------------
    # Boolean values
    # -----------------------------------------------------------------------

    for field in boolean_fields:
        value = row[field]

        if pd.isna(value):
            result[field] = False
        else:
            result[field] = bool(value)

    # -----------------------------------------------------------------------
    # Risk classification
    # -----------------------------------------------------------------------

    result["risk_level"] = str(row["risk_level"])
    result["evidence_status"] = str(row["evidence_status"])

    # -----------------------------------------------------------------------
    # Human-readable reasons
    # -----------------------------------------------------------------------

    for field in (
        "top_reason_1",
        "top_reason_2",
        "top_reason_3",
    ):
        result[field] = _nullable_string(row[field])

    result["risk_reasons"] = _json_list(
        row["risk_reasons"]
    )

    result["source_signal_summary"] = _json_object(
        row["source_signal_summary"],
        {"signals": []},
    )

    return result

def get_project_risk(
    db,
    project_id: str,
) -> dict[str, Any] | None:
    """Compatibility wrapper for the project API.

    The database argument is retained for the existing route contract.
    Risk data remains sourced exclusively from the Phase 9 Risk Fusion
    pipeline.
    """
    return get_risk_fusion_result(project_id)


# ---------------------------------------------------------------------------
# Single-project result
# ---------------------------------------------------------------------------

def get_risk_fusion_result(
    work_id: str,
) -> dict[str, Any] | None:
    """
    Return the current Phase 9 Risk Fusion result for one project.

    Returns:
        dict:
            Risk Fusion result when the project exists in the canonical
            Risk Fusion output.

        None:
            When the requested project does not exist in the Risk Fusion
            output.

    Raises:
        FileNotFoundError:
            If a required upstream Phase 4/5/6 artifact is missing.

        ValueError:
            If an upstream artifact fails Phase 7 validation.

        RuntimeError:
            If Risk Fusion produces an invalid output.
    """

    requested_work_id = str(work_id)

    output = _current_output()

    matches = output[
        output["work_id"].astype(str).eq(requested_work_id)
    ]

    if matches.empty:
        return None

    return _result_from_row(matches.iloc[0])


# ---------------------------------------------------------------------------
# Multiple-project results
# ---------------------------------------------------------------------------

def get_risk_fusion_results(
    work_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    """
    Return current Risk Fusion results for a bounded set of project IDs.

    Risk Fusion itself is executed only once against the complete canonical
    dataset. Requested projects are then looked up from the cached output.
    """

    requested = {
        str(work_id)
        for work_id in work_ids
    }

    if not requested:
        return {}

    output = _current_output()

    output = output[
        output["work_id"].astype(str).isin(requested)
    ]

    results: dict[str, dict[str, Any]] = {}

    for _, row in output.iterrows():
        result = _result_from_row(row)
        results[str(result["work_id"])] = result

    return results


# ---------------------------------------------------------------------------
