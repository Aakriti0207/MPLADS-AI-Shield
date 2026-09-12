"""Request-isolated CSV analysis for Phase 12.

The service adapts common upload column aliases into the existing Phase 2
canonical contract, then calls the unchanged Phase 3-9 engines in memory.
It never writes production or evaluation artifacts.
"""

from __future__ import annotations

import io
import json
import re
from typing import Any

import pandas as pd

from ml.anomalies.engine import build_phase5_outputs
from ml.compliance.engine import build_compliance_outputs
from ml.duplicates.engine import build_phase6_outputs
from ml.features import build_ml_features
from ml.isolation_forest.engine import fit_isolation_forest_model, score_isolation_forest_data
from ml.payment.engine import fit_payment_model, score_payment_data
from ml.risk import build_output, validate_inputs


MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10_000
WORK_ID_PATTERN = re.compile(r"^WS/MP\d+/\d{4}-\d{4}/\d+$")

ALIASES = {
    "work_id": ("work_id", "workid", "project_id", "projectid", "work_no", "work_number", "id"),
    "work_description": ("work_description", "description", "work", "project_description", "project_name"),
    "state": ("state", "state_name"),
    "constituency": ("constituency", "parliamentary_constituency"),
    "mp": ("mp", "mp_name", "member_of_parliament"),
    "implementing_agency": ("implementing_agency", "agency", "executing_agency"),
    "work_category": ("work_category", "work_type", "category", "type"),
    "work_status": ("work_status", "status"),
    "recommended_amount": ("recommended_amount", "recommended", "recommended_cost"),
    "sanction_amount": ("sanction_amount", "sanctioned_amount", "sanctioned", "sanction_amount_rs"),
    "amount_disbursed": ("amount_disbursed", "disbursed_amount", "disbursement"),
    "total_expenditure": ("total_expenditure", "expenditure", "total_spent", "spent_amount"),
    "total_amount_in_progress": ("total_amount_in_progress", "amount_in_progress", "pending_amount"),
    "n_expenditure_transactions": ("n_expenditure_transactions", "expenditure_transactions", "transaction_count"),
    "n_distinct_vendors": ("n_distinct_vendors", "distinct_vendors", "vendor_count"),
    "n_payment_success": ("n_payment_success", "successful_payments", "payment_success_count"),
    "n_payment_in_progress": ("n_payment_in_progress", "pending_payments", "payment_pending_count"),
    "recommended_date": ("recommended_date", "recommendation_date"),
    "sanction_date": ("sanction_date", "sanctioned_date"),
    "completion_date": ("completion_date", "completed_date"),
    "first_expenditure_date": ("first_expenditure_date", "first_payment_date"),
    "last_expenditure_date": ("last_expenditure_date", "last_payment_date"),
}

BOOLEAN_COLUMNS = (
    "has_recommended_record", "has_sanctioned_record", "has_completed_record", "has_expenditure_record",
    "any_field_conflict", "state_conflict", "mp_conflict", "constituency_conflict",
    "implementing_agency_conflict", "work_category_conflict", "work_description_conflict",
    "elected_nominated_conflict", "recommended_date_conflict", "flag_completion_without_sanction",
    "flag_expenditure_without_sanction", "flag_sanction_without_recommendation",
    "flag_completion_before_sanction", "flag_expenditure_before_recommendation",
    "flag_recommendation_after_sanction",
)


class AnalysisInputError(ValueError):
    """A safe, user-facing upload validation error."""


def _normalize_column(value: Any) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())).strip("_")


def _read_upload(raw_bytes: bytes, filename: str) -> pd.DataFrame:
    if not filename.lower().endswith(".csv"):
        raise AnalysisInputError("Only .csv files are accepted.")
    if not raw_bytes:
        raise AnalysisInputError("The uploaded file is empty.")
    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        raise AnalysisInputError(f"The uploaded file exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB limit.")
    try:
        frame = pd.read_csv(io.BytesIO(raw_bytes), dtype=str, keep_default_na=False)
    except Exception as exc:
        raise AnalysisInputError("Unable to parse the uploaded CSV. Check its encoding and header row.") from exc
    if frame.empty:
        raise AnalysisInputError("The uploaded CSV has no data rows.")
    if len(frame) > MAX_ROWS:
        raise AnalysisInputError(f"The uploaded CSV exceeds the {MAX_ROWS:,}-row limit.")
    normalized = [_normalize_column(column) for column in frame.columns]
    if len(normalized) != len(set(normalized)):
        raise AnalysisInputError("The CSV contains duplicate or ambiguous column names.")
    frame.columns = normalized
    return frame


def _alias_map(columns: list[str]) -> dict[str, str]:
    lookup = set(columns)
    result = {}
    for canonical, aliases in ALIASES.items():
        match = next((alias for alias in aliases if alias in lookup), None)
        if match:
            result[canonical] = match
    return result


def _indicator(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _canonicalize(frame: pd.DataFrame) -> pd.DataFrame:
    aliases = _alias_map(list(frame.columns))
    if "work_id" not in aliases:
        raise AnalysisInputError("A project identifier column is required (for example work_id or project_id).")
    canonical = pd.DataFrame(index=frame.index)
    for name, source in aliases.items():
        canonical[name] = frame[source].astype(str).str.strip().replace({"": pd.NA})
    canonical["work_id"] = canonical["work_id"].astype("string")
    if canonical["work_id"].isna().any() or canonical["work_id"].duplicated().any():
        raise AnalysisInputError("Every project must have a non-empty, unique identifier.")

    for name in ("state", "constituency", "mp", "implementing_agency", "work_category", "work_status", "work_description"):
        if name not in canonical:
            canonical[name] = "Not specified"
    for name in ("recommended_amount", "sanction_amount", "amount_disbursed", "total_expenditure", "total_amount_in_progress", "n_expenditure_transactions", "n_distinct_vendors", "n_payment_success", "n_payment_in_progress"):
        canonical[name] = pd.to_numeric(canonical.get(name, pd.Series(pd.NA, index=frame.index)), errors="coerce")
    for name in ("recommended_date", "sanction_date", "completion_date", "first_expenditure_date", "last_expenditure_date"):
        canonical[name] = pd.to_datetime(canonical.get(name, pd.Series(pd.NaT, index=frame.index)), errors="coerce")

    canonical["houses"] = "UPLOAD"
    canonical["elected_nominated"] = "Not specified"
    canonical["stages_present"] = ""
    canonical["has_recommended_record"] = canonical["recommended_date"].notna() | canonical["recommended_amount"].notna()
    canonical["has_sanctioned_record"] = canonical["sanction_date"].notna() | canonical["sanction_amount"].notna()
    canonical["has_completed_record"] = canonical["completion_date"].notna()
    canonical["has_expenditure_record"] = canonical["total_expenditure"].notna() | canonical["first_expenditure_date"].notna()
    canonical["n_lifecycle_stages_present"] = canonical[["has_recommended_record", "has_sanctioned_record", "has_completed_record", "has_expenditure_record"]].sum(axis=1)
    canonical["stages_present"] = canonical[["has_recommended_record", "has_sanctioned_record", "has_completed_record", "has_expenditure_record"]].apply(lambda row: "|".join(name for name, present in zip(("RECOMMENDED", "SANCTIONED", "COMPLETED", "EXPENDITURE"), row) if present), axis=1)
    canonical["any_field_conflict"] = False
    for name in BOOLEAN_COLUMNS:
        if name not in canonical:
            canonical[name] = False
    canonical["flag_completion_before_sanction"] = canonical["completion_date"].notna() & canonical["sanction_date"].notna() & canonical["completion_date"].lt(canonical["sanction_date"])
    canonical["flag_expenditure_before_recommendation"] = canonical["first_expenditure_date"].notna() & canonical["recommended_date"].notna() & canonical["first_expenditure_date"].lt(canonical["recommended_date"])
    canonical["flag_recommendation_after_sanction"] = canonical["recommended_date"].notna() & canonical["sanction_date"].notna() & canonical["recommended_date"].gt(canonical["sanction_date"])
    return canonical


def _empty_duplicate_summary(work_ids: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({
        "work_id": work_ids.astype(str), "exact_match_count": 0, "similar_match_count": 0,
        "highest_similarity_score": pd.Series(float("nan"), index=work_ids.index, dtype="float64"),
        "phase6_status": "NOT_EVALUABLE",
    })


def _risk_inputs(canonical: pd.DataFrame) -> dict[str, pd.DataFrame]:
    features = build_ml_features(canonical)
    findings, compliance_summary = build_compliance_outputs(features)
    anomalies, phase5_summary = build_phase5_outputs(features)
    if canonical["work_id"].astype(str).map(lambda value: bool(WORK_ID_PATTERN.fullmatch(value))).all():
        duplicate_matches, duplicate_summary = build_phase6_outputs(canonical)
    else:
        duplicate_matches = pd.DataFrame(columns=["work_id_a", "work_id_b", "match_type", "similarity_score", "description_frequency_a", "description_frequency_b"])
        duplicate_summary = _empty_duplicate_summary(canonical["work_id"])
    inputs = {
        "canonical": canonical[["work_id"]], "compliance_findings": findings,
        "compliance_summary": compliance_summary,
        "financial_anomalies": anomalies[anomalies["domain"].eq("FINANCIAL")],
        "timeline_anomalies": anomalies[anomalies["domain"].eq("TIMELINE")],
        "phase5_summary": phase5_summary, "duplicate_matches": duplicate_matches,
        "duplicate_summary": duplicate_summary,
    }
    payment_columns = ["work_id", "sanction_amount", "total_expenditure", "total_amount_in_progress", "n_expenditure_transactions", "n_distinct_vendors", "n_payment_success", "n_payment_in_progress", "expenditure_span_days"]
    if len(features) >= 8:
        try:
            payment_model = fit_payment_model(features[payment_columns].iloc[:-1])
            inputs["payment"] = score_payment_data(payment_model, features[payment_columns])
        except ValueError:
            pass
    if len(features) >= 20:
        try:
            isolation_model = fit_isolation_forest_model(features.iloc[:-1])
            inputs["isolation_forest"] = score_isolation_forest_data(isolation_model, features)
        except ValueError:
            pass
    validate_inputs(inputs)
    return inputs


def analyze_csv(raw_bytes: bytes, filename: str) -> dict[str, Any]:
    source = _read_upload(raw_bytes, filename)
    canonical = _canonicalize(source)
    inputs = _risk_inputs(canonical)
    output = build_output(inputs)
    details = canonical.set_index("work_id").reindex(output["work_id"])
    projects = []
    for _, row in output.iterrows():
        reasons = []
        if isinstance(row.get("risk_reasons"), str):
            try:
                reasons = json.loads(row["risk_reasons"])
            except json.JSONDecodeError:
                reasons = [row["risk_reasons"]]
        evidence = [name for name, column in (("compliance", "compliance_contribution"), ("financial", "financial_anomaly_contribution"), ("timeline", "timeline_anomaly_contribution"), ("duplicate", "duplicate_contribution"), ("data_quality", "data_quality_contribution")) if float(row.get(column, 0) or 0) > 0]
        source_row = details.loc[row["work_id"]]
        projects.append({
            "work_id": row["work_id"], "state": source_row.get("state"), "constituency": source_row.get("constituency"),
            "risk_score": float(row["risk_score"]), "risk_level": row["risk_level"],
            "why_risky": reasons, "evidence": evidence,
        })
    counts = output["risk_level"].value_counts().to_dict()
    return {
        "status": "success", "summary": {"total_projects": len(projects), "low": int(counts.get("LOW", 0)), "medium": int(counts.get("MEDIUM", 0)), "high": int(counts.get("HIGH", 0)), "critical": int(counts.get("CRITICAL", 0))},
        "projects": projects,
    }