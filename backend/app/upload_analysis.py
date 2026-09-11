"""
Phase 5: upload parsing, validation, and analysis for POST /upload-analyze.

Audit summary (see the module docstring addition in app/schemas.py for
the full reasoning): the real Project.risk_score/risk_level are produced
by an offline pipeline outside this repository. What this module
genuinely reuses, unmodified, is ml/compliance/rules.py's 12 pure
per-row rule evaluators via ml/compliance/engine.py's
build_compliance_outputs(). Those rules need a small, specific set of
derived "Phase 3 feature" columns (day-counts, date-availability flags,
chronology flags) -- _build_feature_row() below derives exactly those
columns from the raw fields an uploader supplies. This is glue/
preprocessing, not a new scoring algorithm: every actual PASS/FLAG/
NOT_EVALUABLE decision and every threshold (45 days, 365 days, ₹2.5
lakh, etc.) comes from ml/compliance/rules.py itself, untouched.

Explicitly OUT of scope here (see Deferred in the Phase 5 report):
- Anomaly/peer-comparison scoring (ml/anomalies) -- requires statistical
  baselines fit across the whole corpus, not a single new row.
- Duplicate/similarity detection (ml/duplicates) -- requires a
  work_description field (which Project does not even store) and a
  TF-IDF fit across the whole corpus; re-fitting that per request would
  not be genuine reuse, it would be reinventing a batch algorithm as if
  it were real-time.
Both would require inventing behavior the existing code does not
support at single-project granularity, which Phase 5's scope rules
prohibit.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Project
from ml.compliance.engine import build_compliance_outputs

# --- Upload limits (practical MVP protections, not production hardening) -

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_ROWS = 500

REQUIRED_COLUMNS = {"work_id"}
NUMERIC_COLUMNS = (
    "sanctioned_amount",
    "recommended_amount",
    "amount_disbursed",
    "expenditure",
    "estimated_cost",
)
DATE_COLUMNS = (
    "recommended_date",
    "sanction_date",
    "completion_date",
    "first_expenditure_date",
)
# Descriptive columns that are passed through for display only -- they do
# not feed the compliance rules at all.
PASSTHROUGH_COLUMNS = ("state", "work_type", "implementing_agency", "status")

ALL_KNOWN_COLUMNS = (
    {"work_id"} | set(NUMERIC_COLUMNS) | set(DATE_COLUMNS) | set(PASSTHROUGH_COLUMNS)
)


class UploadFormatError(ValueError):
    """Raised for file-level problems (empty file, unreadable CSV,
    missing required column, too many rows, duplicate work_id across
    rows). Distinct from per-row validation errors, which never raise --
    they're collected per row instead so one bad row doesn't fail the
    whole file."""


@dataclass
class ParsedRow:
    row_number: int
    work_id: Optional[str]
    errors: list[tuple[str, str]]  # (field, message)
    values: dict[str, Any]  # cleaned values, only for fields that parsed OK


def read_and_validate_csv(raw_bytes: bytes, filename: str) -> pd.DataFrame:
    """File-level validation. Raises UploadFormatError with a clear,
    user-facing message on any problem; never leaks a stack trace or a
    filesystem path."""
    if not filename.lower().endswith(".csv"):
        raise UploadFormatError("Only .csv files are accepted.")

    if len(raw_bytes) == 0:
        raise UploadFormatError("The uploaded file is empty.")

    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        raise UploadFormatError(
            f"The uploaded file is too large ({len(raw_bytes)} bytes). "
            f"The maximum accepted size is {MAX_FILE_SIZE_BYTES} bytes."
        )

    try:
        # dtype=str: every column is read as text first; this module does
        # its own explicit numeric/date parsing per field below rather than
        # trusting pandas' automatic type inference, so a malformed cell
        # becomes a clear per-row validation error instead of a silently
        # wrong value or a NaN swallowed a layer too early.
        df = pd.read_csv(
            io.BytesIO(raw_bytes), dtype=str, keep_default_na=False, index_col=False
        )
    except Exception as exc:  # pandas raises several distinct error types
        raise UploadFormatError(
            "The file could not be parsed as CSV. Please check that it is a "
            "well-formed, comma-separated file with a header row."
        ) from exc

    if df.shape[1] == 0 or df.shape[0] == 0:
        raise UploadFormatError("The uploaded CSV has no data rows.")

    if len(df) > MAX_ROWS:
        raise UploadFormatError(
            f"The uploaded CSV has {len(df)} rows, which exceeds the "
            f"maximum of {MAX_ROWS} rows per upload."
        )

    missing_required = REQUIRED_COLUMNS - set(df.columns)
    if missing_required:
        raise UploadFormatError(
            "The CSV is missing required column(s): " + ", ".join(sorted(missing_required))
        )

    # Duplicate column headers (e.g. two "work_id" columns) make every
    # downstream lookup ambiguous -- reject the whole file rather than
    # silently picking one.
    duplicate_headers = df.columns[df.columns.duplicated()].tolist()
    if duplicate_headers:
        raise UploadFormatError(
            "The CSV has duplicate column header(s): " + ", ".join(sorted(set(duplicate_headers)))
        )

    work_ids = df["work_id"].astype(str).str.strip()
    non_empty_ids = work_ids[work_ids != ""]
    duplicated = non_empty_ids[non_empty_ids.duplicated()].unique().tolist()
    if duplicated:
        raise UploadFormatError(
            "The CSV has duplicate work_id value(s): " + ", ".join(sorted(duplicated))
        )

    return df


def _parse_decimal(raw: str) -> Optional[Decimal]:
    raw = raw.strip()
    if raw == "":
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        raise ValueError(f"'{raw}' is not a valid number")


def _parse_date(raw: str):
    raw = raw.strip()
    if raw == "":
        return None
    parsed = pd.to_datetime(raw, errors="coerce")
    if pd.isna(parsed):
        raise ValueError(f"'{raw}' is not a recognizable date (expected e.g. YYYY-MM-DD)")
    return parsed


def parse_row(row_number: int, row: "pd.Series") -> ParsedRow:
    """Validate and clean one CSV row. Never raises -- every problem is
    collected as a (field, message) pair so the row can be reported
    without aborting the rest of the upload."""
    errors: list[tuple[str, str]] = []
    values: dict[str, Any] = {}

    work_id = str(row.get("work_id", "")).strip()
    if not work_id:
        errors.append(("work_id", "work_id is required and cannot be blank."))
        work_id = None

    for col in NUMERIC_COLUMNS:
        raw = str(row.get(col, "")) if col in row.index else ""
        try:
            values[col] = _parse_decimal(raw)
        except ValueError as exc:
            errors.append((col, str(exc)))

    for col in DATE_COLUMNS:
        raw = str(row.get(col, "")) if col in row.index else ""
        try:
            values[col] = _parse_date(raw)
        except ValueError as exc:
            errors.append((col, str(exc)))

    for col in PASSTHROUGH_COLUMNS:
        raw = str(row.get(col, "")).strip() if col in row.index else ""
        values[col] = raw or None

    return ParsedRow(row_number=row_number, work_id=work_id, errors=errors, values=values)


def compute_basic_metrics(values: dict[str, Any]) -> dict[str, Any]:
    """Plain arithmetic over the uploader's own numbers -- not part of
    the compliance engine, not a risk score. None where the inputs
    needed weren't supplied."""
    sanctioned = values.get("sanctioned_amount")
    expenditure = values.get("expenditure")

    financial_progress_percent = None
    exceeds = None
    if sanctioned is not None and sanctioned > 0 and expenditure is not None:
        financial_progress_percent = (expenditure / sanctioned) * Decimal("100")
        exceeds = expenditure > sanctioned

    return {
        "financial_progress_percent": financial_progress_percent,
        "expenditure_exceeds_sanctioned_amount": exceeds,
    }


def _build_feature_row(work_id: str, values: dict[str, Any]) -> dict[str, Any]:
    """Derive exactly the columns ml/compliance/engine.py's
    REQUIRED_COLUMNS needs, from the raw fields an uploader supplies.
    This is the one piece of new logic in this module -- everything it
    produces is a simple, documented, deterministic derivation (day
    counts, presence flags, chronology comparisons), not a scoring
    decision. Every actual PASS/FLAG/threshold decision still happens
    inside ml/compliance/rules.py, unmodified.
    """
    recommended_date = values.get("recommended_date")
    sanction_date = values.get("sanction_date")
    completion_date = values.get("completion_date")
    first_expenditure_date = values.get("first_expenditure_date")

    def days_between(later, earlier):
        if later is None or earlier is None:
            return None
        return (later - earlier).days

    def before(a, b):
        """True if a occurred before b; None if either is missing."""
        if a is None or b is None:
            return None
        return bool(a < b)

    return {
        "work_id": work_id,
        "recommended_amount": values.get("recommended_amount"),
        "sanction_amount": values.get("sanctioned_amount"),
        "amount_disbursed": values.get("amount_disbursed"),
        "total_expenditure": values.get("expenditure"),
        "recommendation_to_sanction_days": days_between(sanction_date, recommended_date),
        "sanction_to_completion_days": days_between(completion_date, sanction_date),
        "is_recommended_date_available": recommended_date is not None,
        "is_sanction_date_available": sanction_date is not None,
        "is_completion_date_available": completion_date is not None,
        "is_first_expenditure_date_available": first_expenditure_date is not None,
        "flag_completion_before_sanction": before(completion_date, sanction_date),
        "flag_expenditure_before_recommendation": before(first_expenditure_date, recommended_date),
        "flag_recommendation_after_sanction": before(sanction_date, recommended_date),
        # A single freshly uploaded record has exactly one source, so
        # there is no second source it could conflict with -- this is a
        # genuinely known "no conflict" (False), not an unknown. DQ01
        # only exists to catch conflicts BETWEEN multiple source files
        # during the real Phase 2 import, which does not apply here.
        "any_field_conflict": False,
    }


def run_compliance_for_row(work_id: str, values: dict[str, Any]) -> dict[str, Any]:
    """Run the real ml/compliance rule engine on one uploaded project.
    Returns the same shape build_compliance_outputs's summary row has,
    plus the individual findings."""
    feature_row = _build_feature_row(work_id, values)
    features_df = pd.DataFrame([feature_row])
    findings_df, summary_df = build_compliance_outputs(features_df)

    findings = [
        {
            "rule_id": f["rule_id"],
            "category": f["category"],
            "status": f["status"],
            "severity": f["severity"],
            "message": f["message"],
            "evidence": _json_loads_or_empty(f["evidence_json"]),
        }
        for f in findings_df.to_dict(orient="records")
    ]
    summary = summary_df.iloc[0].to_dict()
    summary["findings"] = findings
    return summary


def _json_loads_or_empty(raw: str) -> dict:
    import json

    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return {}


def existing_project_ids(db: Session, work_ids: list[str]) -> set[str]:
    """Single bounded query against the real `projects` table -- looks
    up only the work_ids present in this upload, never scans all 56,323
    rows."""
    if not work_ids:
        return set()
    rows = db.execute(
        select(Project.project_id).where(Project.project_id.in_(work_ids))
    ).all()
    return {r[0] for r in rows}