"""
Phase 2 — Canonical project lifecycle status resolution (ML-1).

`ml.canonical` pulls `work_status` straight from the Works Sanctioned
dataset (via COLUMN_MAPPINGS[SANCTIONED]["work_status"]). That value is a
snapshot of the Sanctioned-stage record only, and is NOT reconciled
against the Works Completed dataset. A project can therefore carry a
stale Sanctioned-stage `work_status` (e.g. "Physical Inspection") even
though a later Works Completed record exists for the same Work ID
(`has_completed_record=True`, `completion_date` populated) -- confirmed
on WS/MP1/2023-2024/103702.

This module derives ONE deterministic, backend/database/dashboard-facing
lifecycle `status` from the already-reconciled canonical fields, without
ever overwriting the raw `work_status` column:

    COMPLETED / ONGOING / SANCTIONED / RECOMMENDED / NOT_SPECIFIED

RESOLUTION PRECEDENCE (first match wins -- see resolve_status_frame):

  1. has_completed_record is True                       -> COMPLETED
     A matching Works Completed row always overrides a stale
     Sanctioned-stage work_status.
  2. work_status == "Work Completed"                     -> COMPLETED
     Explicit even without a matching Works Completed row.
  3. work_status == "Work partially Completed"           -> ONGOING
  4. work_status == "Physical Inspection"                -> ONGOING
  5. work_status in {"Vendor Identification", "Sanction",
                      "Time Estimation"}
     OR has_sanctioned_record is True (any other/unrecognized
     Sanctioned-stage text)                               -> SANCTIONED
  6. has_recommended_record is True                       -> RECOMMENDED
  7. none of the above (no lifecycle evidence at all)      -> NOT_SPECIFIED

Rules 1-5's exact work_status literals are the confirmed raw Sanctioned-
stage values (Physical Inspection, Vendor Identification, Sanction, Work
partially Completed, Work Completed, Time Estimation -- ~33k rows
combined after footer-row exclusion). The `has_sanctioned_record`
fallback inside rule 5 is defensive insurance for a future/unlisted
Sanctioned-stage text value; it is never needed against the currently
confirmed data since those six literals are exhaustive there.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

STATUS_COMPLETED = "COMPLETED"
STATUS_ONGOING = "ONGOING"
STATUS_SANCTIONED = "SANCTIONED"
STATUS_RECOMMENDED = "RECOMMENDED"
STATUS_NOT_SPECIFIED = "NOT_SPECIFIED"

CANONICAL_STATUSES = (
    STATUS_COMPLETED,
    STATUS_ONGOING,
    STATUS_SANCTIONED,
    STATUS_RECOMMENDED,
    STATUS_NOT_SPECIFIED,
)

# Raw Sanctioned-stage `work_status` literals, confirmed against the
# actual raw data (see module docstring).
WORK_STATUS_EXPLICIT_COMPLETED = "Work Completed"
WORK_STATUS_ONGOING_VALUES = {"Work partially Completed", "Physical Inspection"}
WORK_STATUS_SANCTIONED_VALUES = {"Vendor Identification", "Sanction", "Time Estimation"}

REQUIRED_STATUS_INPUT_COLUMNS = frozenset(
    {"work_status", "has_completed_record", "has_sanctioned_record", "has_recommended_record"}
)


def _bool_series(canonical: pd.DataFrame, column: str) -> pd.Series:
    """Treat missing/NaN as False -- 'no evidence' rather than 'unknown'."""
    return canonical[column].fillna(False).astype(bool)


def resolve_status_frame(canonical: pd.DataFrame) -> pd.Series:
    """Vectorized implementation of the precedence documented above.

    Expects REQUIRED_STATUS_INPUT_COLUMNS to already be present (built by
    ml.canonical.build_canonical_dataset() before this is called). Never
    mutates `canonical` or its `work_status` column -- returns a new
    Series to be assigned to a separate `status` column.
    """
    missing = sorted(REQUIRED_STATUS_INPUT_COLUMNS - set(canonical.columns))
    if missing:
        raise ValueError("resolve_status_frame is missing required columns: " + ", ".join(missing))

    work_status = canonical["work_status"].astype("string")
    has_completed = _bool_series(canonical, "has_completed_record")
    has_sanctioned = _bool_series(canonical, "has_sanctioned_record")
    has_recommended = _bool_series(canonical, "has_recommended_record")

    is_explicit_completed = work_status.eq(WORK_STATUS_EXPLICIT_COMPLETED).fillna(False)
    is_ongoing_status = work_status.isin(WORK_STATUS_ONGOING_VALUES).fillna(False)
    is_sanctioned_status = work_status.isin(WORK_STATUS_SANCTIONED_VALUES).fillna(False)

    conditions = [
        has_completed,                              # Rule 1
        is_explicit_completed,                       # Rule 2
        is_ongoing_status,                            # Rules 3 & 4
        is_sanctioned_status | has_sanctioned,         # Rule 5
        has_recommended,                              # Rule 6
    ]
    choices = [
        STATUS_COMPLETED,
        STATUS_COMPLETED,
        STATUS_ONGOING,
        STATUS_SANCTIONED,
        STATUS_RECOMMENDED,
    ]
    resolved = np.select(conditions, choices, default=STATUS_NOT_SPECIFIED)
    return pd.Series(resolved, index=canonical.index, dtype="string", name="status")
