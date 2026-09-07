"""Robust, reproducible peer statistics for Phase 5."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


MIN_PEERS = 20
MODIFIED_Z_THRESHOLD = 3.5
SKEW_THRESHOLD = 1.0


@dataclass(frozen=True)
class PeerBaseline:
    level: str | None
    key: str | None
    size: int
    median: float | None
    mad: float | None
    q1: float | None
    q3: float | None
    transformation: str


@dataclass(frozen=True)
class PeerIndex:
    """Cached valid row indices for each deterministic peer-group level."""

    groups: dict[str, dict[object, np.ndarray]]
    valid_indices: np.ndarray
    row_keys: dict[str, tuple[object | None, ...]]


def _finite(values: np.ndarray) -> np.ndarray:
    return values[np.isfinite(values)]


def should_log1p(values: np.ndarray, metric_name: str) -> bool:
    """Use log1p only for nonnegative, strongly right-skewed absolute amounts."""
    absolute_amounts = {
        "recommended_amount", "sanction_amount", "amount_disbursed",
        "total_expenditure", "total_amount_in_progress",
    }
    values = _finite(values)
    return (
        metric_name in absolute_amounts
        and len(values) >= MIN_PEERS
        and np.all(values >= 0)
        and float(np.mean(values)) > 0
        and float(np.std(values)) > 0
        and float(np.mean(((values - np.mean(values)) / np.std(values)) ** 3)) > SKEW_THRESHOLD
    )


def choose_peer_level(
    index: int,
    frame,
    valid_mask,
    state_column: str = "state",
    category_column: str = "work_category",
) -> tuple[str | None, str | None, np.ndarray]:
    """Compatibility wrapper returning a boolean mask for one row."""
    peer_index = build_peer_index(frame, valid_mask, state_column, category_column)
    level, key, peer_indices = choose_peer_indices(index, peer_index)
    mask = np.zeros(len(frame), dtype=bool)
    mask[peer_indices] = True
    return level, key, mask


def build_peer_index(
    frame,
    valid_mask,
    state_column: str = "state",
    category_column: str = "work_category",
) -> PeerIndex:
    """Precompute valid row membership for all peer levels once."""
    valid_indices = np.flatnonzero(np.asarray(valid_mask, dtype=bool))
    state_values = frame[state_column].tolist()
    category_values = frame[category_column].tolist()
    row_keys: dict[str, tuple[object | None, ...]] = {
        "state": tuple(None if _is_missing(value) else str(value) for value in state_values),
        "work_category": tuple(None if _is_missing(value) else str(value) for value in category_values),
    }
    row_keys["state_work_category"] = tuple(
        None if state is None or category is None else f"{state}|{category}"
        for state, category in zip(row_keys["state"], row_keys["work_category"])
    )
    groups: dict[str, dict[object, np.ndarray]] = {
        "state_work_category": {}, "state": {}, "work_category": {},
    }
    for level in ("state_work_category", "state", "work_category"):
        for row_index in valid_indices:
            key = row_keys[level][row_index]
            if key is not None:
                groups[level].setdefault(key, []).append(row_index)
        groups[level] = {key: np.asarray(indices, dtype=np.int64) for key, indices in groups[level].items()}
    groups["global"] = {"GLOBAL": valid_indices.copy()}
    return PeerIndex(groups, valid_indices, row_keys)


def choose_peer_indices(index: int, peer_index: PeerIndex) -> tuple[str | None, str | None, np.ndarray]:
    """Return cached leave-one-out indices using the fixed hierarchy."""
    for level in ("state_work_category", "state", "work_category", "global"):
        key = "GLOBAL" if level == "global" else peer_index.row_keys[level][index]
        if key is None:
            continue
        group_indices = peer_index.groups[level].get(key)
        if group_indices is None:
            continue
        peer_count = len(group_indices) - int(index in group_indices)
        if peer_count >= MIN_PEERS:
            if index in group_indices:
                return level, key, group_indices[group_indices != index]
            return level, key, group_indices
    return None, None, np.empty(0, dtype=np.int64)


def _is_missing(value) -> bool:
    try:
        return bool(np.asarray(value != value).item())
    except (TypeError, ValueError):
        return value is None


def build_baseline(values: np.ndarray, metric_name: str, level: str, key: str, size: int) -> PeerBaseline:
    transform = "log1p" if should_log1p(values, metric_name) else "none"
    transformed = np.log1p(values) if transform == "log1p" else values
    median = float(np.median(transformed))
    deviations = np.abs(transformed - median)
    mad = float(np.median(deviations))
    q1, q3 = np.percentile(transformed, [25, 75])
    return PeerBaseline(level, key, size, median, mad, float(q1), float(q3), transform)


def evaluate_value(observed: float, baseline: PeerBaseline) -> dict:
    """Evaluate exactly one decision method; never combine z and IQR rules."""
    if observed is None or not np.isfinite(observed) or baseline.level is None:
        return {"status": "NOT_EVALUABLE", "direction": "NONE", "modified_z_score": None, "lower_bound": None, "upper_bound": None, "decision_method": "not_evaluable"}

    transformed = float(np.log1p(observed)) if baseline.transformation == "log1p" else float(observed)
    if baseline.mad and baseline.mad > 0:
        score = 0.6745 * (transformed - baseline.median) / baseline.mad
        status = "ANOMALY" if abs(score) >= MODIFIED_Z_THRESHOLD else "NORMAL"
        direction = "HIGH" if score >= MODIFIED_Z_THRESHOLD else "LOW" if score <= -MODIFIED_Z_THRESHOLD else "NONE"
        return {"status": status, "direction": direction, "modified_z_score": float(score), "lower_bound": None, "upper_bound": None, "decision_method": "modified_z_score"}

    if transformed == baseline.median:
        return {"status": "NORMAL", "direction": "NONE", "modified_z_score": None, "lower_bound": None, "upper_bound": None, "decision_method": "modified_z_score"}

    iqr = baseline.q3 - baseline.q1
    if iqr > 0:
        lower = baseline.q1 - 1.5 * iqr
        upper = baseline.q3 + 1.5 * iqr
        status = "ANOMALY" if transformed < lower or transformed > upper else "NORMAL"
        direction = "HIGH" if transformed > upper else "LOW" if transformed < lower else "NONE"
        return {"status": status, "direction": direction, "modified_z_score": None, "lower_bound": float(lower), "upper_bound": float(upper), "decision_method": "iqr_fallback"}
    return {"status": "NOT_EVALUABLE", "direction": "NONE", "modified_z_score": None, "lower_bound": None, "upper_bound": None, "decision_method": "not_evaluable"}