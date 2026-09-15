from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.anomalies.engine import ANOMALY_COLUMNS, SUMMARY_COLUMNS
from ml.anomalies.financial import FINANCIAL_METRICS
from ml.anomalies.statistics import (
    MIN_PEERS,
    build_baseline,
    build_peer_index,
    evaluate_value,
)
from ml.anomalies.timeline import TIMELINE_METRICS
from ml.compliance.engine import build_compliance_outputs
from ml.duplicates.engine import build_phase6_outputs
from ml.features import build_ml_features
from ml.status import resolve_status_frame
from ml.isolation_forest.engine import (
    fit_isolation_forest_model,
    score_isolation_forest_data,
)
from ml.payment.engine import fit_payment_model, score_payment_data
from ml.risk import build_output, validate_inputs
from ml.config import BACKEND_ROOT


MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10_000

WORK_ID_PATTERN = re.compile(r"^WS/MP\d+/\d{4}-\d{4}/\d+$")

PROCESSED_DIR = BACKEND_ROOT / "data" / "processed"
HISTORICAL_FEATURES_PATH = PROCESSED_DIR / "ml_features.csv"
HISTORICAL_CANONICAL_PATH = PROCESSED_DIR / "canonical_projects.csv"


ALIASES = {
    "work_id": (
        "work_id",
        "workid",
        "project_id",
        "projectid",
        "work_no",
        "work_number",
        "id",
    ),
    "work_description": (
        "work_description",
        "description",
        "work",
        "project_description",
        "project_name",
    ),
    "state": ("state", "state_name"),
    "constituency": ("constituency", "parliamentary_constituency"),
    "mp": ("mp", "mp_name", "member_of_parliament"),
    "implementing_agency": (
        "implementing_agency",
        "agency",
        "executing_agency",
    ),
    "work_category": (
        "work_category",
        "work_type",
        "category",
        "type",
    ),
    "work_status": ("work_status", "status"),
    "recommended_amount": (
        "recommended_amount",
        "recommended",
        "recommended_cost",
    ),
    "sanction_amount": (
        "sanction_amount",
        "sanctioned_amount",
        "sanctioned",
        "sanction_amount_rs",
    ),
    "amount_disbursed": (
        "amount_disbursed",
        "disbursed_amount",
        "disbursement",
    ),
    "total_expenditure": (
        "total_expenditure",
        "expenditure",
        "total_spent",
        "spent_amount",
    ),
    "total_amount_in_progress": (
        "total_amount_in_progress",
        "amount_in_progress",
        "pending_amount",
    ),
    "n_expenditure_transactions": (
        "n_expenditure_transactions",
        "expenditure_transactions",
        "transaction_count",
    ),
    "n_distinct_vendors": (
        "n_distinct_vendors",
        "distinct_vendors",
        "vendor_count",
    ),
    "n_payment_success": (
        "n_payment_success",
        "successful_payments",
        "payment_success_count",
    ),
    "n_payment_in_progress": (
        "n_payment_in_progress",
        "pending_payments",
        "payment_pending_count",
    ),
    "recommended_date": (
        "recommended_date",
        "recommendation_date",
    ),
    "sanction_date": (
        "sanction_date",
        "sanctioned_date",
    ),
    "completion_date": (
        "completion_date",
        "completed_date",
    ),
    "first_expenditure_date": (
        "first_expenditure_date",
        "first_payment_date",
    ),
    "last_expenditure_date": (
        "last_expenditure_date",
        "last_payment_date",
    ),
}


BOOLEAN_COLUMNS = (
    "has_recommended_record",
    "has_sanctioned_record",
    "has_completed_record",
    "has_expenditure_record",
    "any_field_conflict",
    "state_conflict",
    "mp_conflict",
    "constituency_conflict",
    "implementing_agency_conflict",
    "work_category_conflict",
    "work_description_conflict",
    "elected_nominated_conflict",
    "recommended_date_conflict",
    "flag_completion_without_sanction",
    "flag_expenditure_without_sanction",
    "flag_sanction_without_recommendation",
    "flag_completion_before_sanction",
    "flag_expenditure_before_recommendation",
    "flag_recommendation_after_sanction",
)


class AnalysisInputError(ValueError):
    """A safe, user-facing upload validation error."""


def _normalize_column(value: Any) -> str:
    return re.sub(
        r"_+",
        "_",
        re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()),
    ).strip("_")


def _read_upload(raw_bytes: bytes, filename: str) -> pd.DataFrame:
    if not filename.lower().endswith(".csv"):
        raise AnalysisInputError("Only .csv files are accepted.")

    if not raw_bytes:
        raise AnalysisInputError("The uploaded file is empty.")

    if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
        raise AnalysisInputError(
            f"The uploaded file exceeds the "
            f"{MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB limit."
        )

    try:
        frame = pd.read_csv(
            io.BytesIO(raw_bytes),
            dtype=str,
            keep_default_na=False,
        )
    except Exception as exc:
        raise AnalysisInputError(
            "Unable to parse the uploaded CSV. "
            "Check its encoding and header row."
        ) from exc

    if frame.empty:
        raise AnalysisInputError("The uploaded CSV has no data rows.")

    if len(frame) > MAX_ROWS:
        raise AnalysisInputError(
            f"The uploaded CSV exceeds the {MAX_ROWS:,}-row limit."
        )

    normalized = [_normalize_column(column) for column in frame.columns]

    if len(normalized) != len(set(normalized)):
        raise AnalysisInputError(
            "The CSV contains duplicate or ambiguous column names."
        )

    frame.columns = normalized
    return frame


def _alias_map(columns: list[str]) -> dict[str, str]:
    lookup = set(columns)
    result = {}

    for canonical, aliases in ALIASES.items():
        match = next(
            (alias for alias in aliases if alias in lookup),
            None,
        )
        if match:
            result[canonical] = match

    return result


def _canonicalize(frame: pd.DataFrame) -> pd.DataFrame:
    aliases = _alias_map(list(frame.columns))

    if "work_id" not in aliases:
        raise AnalysisInputError(
            "A project identifier column is required "
            "(for example work_id or project_id)."
        )

    canonical = pd.DataFrame(index=frame.index)

    for name, source in aliases.items():
        canonical[name] = (
            frame[source]
            .astype(str)
            .str.strip()
            .replace({"": pd.NA})
        )

    canonical["work_id"] = canonical["work_id"].astype("string")

    if (
        canonical["work_id"].isna().any()
        or canonical["work_id"].duplicated().any()
    ):
        raise AnalysisInputError(
            "Every project must have a non-empty, unique identifier."
        )

    for name in (
        "state",
        "constituency",
        "mp",
        "implementing_agency",
        "work_category",
        "work_status",
        "work_description",
    ):
        if name not in canonical:
            canonical[name] = "Not specified"

    for name in (
        "recommended_amount",
        "sanction_amount",
        "amount_disbursed",
        "total_expenditure",
        "total_amount_in_progress",
        "n_expenditure_transactions",
        "n_distinct_vendors",
        "n_payment_success",
        "n_payment_in_progress",
    ):
        canonical[name] = pd.to_numeric(
            canonical.get(
                name,
                pd.Series(pd.NA, index=frame.index),
            ),
            errors="coerce",
        )

    for name in (
        "recommended_date",
        "sanction_date",
        "completion_date",
        "first_expenditure_date",
        "last_expenditure_date",
    ):
        canonical[name] = pd.to_datetime(
            canonical.get(
                name,
                pd.Series(pd.NaT, index=frame.index),
            ),
            errors="coerce",
        )

    canonical["houses"] = "UPLOAD"
    canonical["elected_nominated"] = "Not specified"
    canonical["stages_present"] = ""

    canonical["has_recommended_record"] = (
        canonical["recommended_date"].notna()
        | canonical["recommended_amount"].notna()
    )

    canonical["has_sanctioned_record"] = (
        canonical["sanction_date"].notna()
        | canonical["sanction_amount"].notna()
    )

    canonical["has_completed_record"] = (
        canonical["completion_date"].notna()
    )

    canonical["has_expenditure_record"] = (
        canonical["total_expenditure"].notna()
        | canonical["first_expenditure_date"].notna()
    )

    lifecycle_flags = [
        "has_recommended_record",
        "has_sanctioned_record",
        "has_completed_record",
        "has_expenditure_record",
    ]

    canonical["n_lifecycle_stages_present"] = canonical[
        lifecycle_flags
    ].sum(axis=1)

    canonical["stages_present"] = canonical[lifecycle_flags].apply(
        lambda row: "|".join(
            name
            for name, present in zip(
                (
                    "RECOMMENDED",
                    "SANCTIONED",
                    "COMPLETED",
                    "EXPENDITURE",
                ),
                row,
            )
            if present
        ),
        axis=1,
    )

    canonical["status"] = resolve_status_frame(canonical)

    canonical["any_field_conflict"] = False

    for name in BOOLEAN_COLUMNS:
        if name not in canonical:
            canonical[name] = False

    canonical["flag_completion_before_sanction"] = (
        canonical["completion_date"].notna()
        & canonical["sanction_date"].notna()
        & canonical["completion_date"].lt(
            canonical["sanction_date"]
        )
    )

    canonical["flag_expenditure_before_recommendation"] = (
        canonical["first_expenditure_date"].notna()
        & canonical["recommended_date"].notna()
        & canonical["first_expenditure_date"].lt(
            canonical["recommended_date"]
        )
    )

    canonical["flag_recommendation_after_sanction"] = (
        canonical["recommended_date"].notna()
        & canonical["sanction_date"].notna()
        & canonical["recommended_date"].gt(
            canonical["sanction_date"]
        )
    )

    return canonical


# ---------------------------------------------------------------------------
# Historical reference data
# ---------------------------------------------------------------------------

def _load_historical_features() -> pd.DataFrame:
    if not HISTORICAL_FEATURES_PATH.exists():
        raise AnalysisInputError(
            "Historical ML features are unavailable. "
            "Run the production ML pipeline before analyzing uploads."
        )

    try:
        historical = pd.read_csv(HISTORICAL_FEATURES_PATH)
    except Exception as exc:
        raise AnalysisInputError(
            "Unable to load the historical ML feature baseline."
        ) from exc

    if historical.empty:
        raise AnalysisInputError(
            "The historical ML feature baseline is empty."
        )

    if "work_id" not in historical.columns:
        raise AnalysisInputError(
            "Historical ML features are missing work_id."
        )

    if historical["work_id"].isna().any() or not historical["work_id"].is_unique:
        raise AnalysisInputError(
            "Historical ML features must contain unique work_id values."
        )

    return historical.reset_index(drop=True)


def _load_historical_canonical() -> pd.DataFrame:
    if not HISTORICAL_CANONICAL_PATH.exists():
        raise AnalysisInputError(
            "Historical canonical projects are unavailable. "
            "Run the production canonicalization pipeline first."
        )

    try:
        historical = pd.read_csv(HISTORICAL_CANONICAL_PATH)
    except Exception as exc:
        raise AnalysisInputError(
            "Unable to load the historical canonical project corpus."
        ) from exc

    required = {
        "work_id",
        "work_description",
        "state",
        "constituency",
        "mp",
        "implementing_agency",
        "recommended_amount",
        "sanction_amount",
    }

    missing = sorted(required - set(historical.columns))
    if missing:
        raise AnalysisInputError(
            "Historical canonical projects are missing required columns: "
            + ", ".join(missing)
        )

    if historical["work_id"].isna().any() or not historical["work_id"].is_unique:
        raise AnalysisInputError(
            "Historical canonical projects must have unique work_id values."
        )

    return historical.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Phase 5: score upload rows against historical peer baselines
# ---------------------------------------------------------------------------

def _valid_for_metric(
    values: pd.Series,
    metric_name: str,
) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")

    valid = numeric.notna() & np.isfinite(numeric)

    if metric_name in {
        "recommended_amount",
        "sanction_amount",
        "amount_disbursed",
        "total_expenditure",
        "total_amount_in_progress",
    }:
        valid &= numeric >= 0

    if metric_name in TIMELINE_METRICS:
        valid &= numeric >= 0

    return valid


def _historical_peer_indices(
    row: pd.Series,
    historical_peer_index,
) -> tuple[str | None, str | None, np.ndarray]:
    state = row.get("state")
    category = row.get("work_category")

    state_key = (
        None
        if pd.isna(state)
        else str(state)
    )
    category_key = (
        None
        if pd.isna(category)
        else str(category)
    )

    state_category_key = (
        None
        if state_key is None or category_key is None
        else f"{state_key}|{category_key}"
    )

    candidates = (
        ("state_work_category", state_category_key),
        ("state", state_key),
        ("work_category", category_key),
        ("global", "GLOBAL"),
    )

    for level, key in candidates:
        if key is None:
            continue

        indices = historical_peer_index.groups.get(level, {}).get(key)

        if indices is not None and len(indices) >= MIN_PEERS:
            return level, key, indices

    return None, None, np.empty(0, dtype=np.int64)


def _score_upload_metric(
    upload: pd.DataFrame,
    historical: pd.DataFrame,
    metric_name: str,
    domain: str,
) -> list[dict[str, Any]]:
    historical_values = pd.to_numeric(
        historical[metric_name],
        errors="coerce",
    )

    historical_valid = _valid_for_metric(
        historical[metric_name],
        metric_name,
    )

    peer_index = build_peer_index(
        historical,
        historical_valid.to_numpy(),
    )

    upload_values = pd.to_numeric(
        upload[metric_name],
        errors="coerce",
    )

    upload_valid = _valid_for_metric(
        upload[metric_name],
        metric_name,
    )

    rows: list[dict[str, Any]] = []

    for upload_index, upload_row in upload.iterrows():
        observed = upload_values.iloc[upload_index]

        if (
            metric_name in TIMELINE_METRICS
            and pd.notna(observed)
            and np.isfinite(float(observed))
            and float(observed) < 0
        ):
            result = {
                "status": "NOT_EVALUABLE",
                "direction": "NONE",
                "modified_z_score": None,
                "lower_bound": None,
                "upper_bound": None,
                "decision_method": "not_evaluable",
            }
            baseline = None
            evidence_reason = "negative_duration_delegated_to_phase4"

        elif not upload_valid.iloc[upload_index]:
            result = {
                "status": "NOT_EVALUABLE",
                "direction": "NONE",
                "modified_z_score": None,
                "lower_bound": None,
                "upper_bound": None,
                "decision_method": "not_evaluable",
            }
            baseline = None
            evidence_reason = "missing_observed_value"

        else:
            level, key, peer_indices = _historical_peer_indices(
                upload_row,
                peer_index,
            )

            if level is None:
                result = {
                    "status": "NOT_EVALUABLE",
                    "direction": "NONE",
                    "modified_z_score": None,
                    "lower_bound": None,
                    "upper_bound": None,
                    "decision_method": "not_evaluable",
                }
                baseline = None
                evidence_reason = "insufficient_historical_peer_group"
            else:
                baseline = build_baseline(
                    historical_values.iloc[peer_indices].to_numpy(dtype=float),
                    metric_name,
                    level,
                    key,
                    len(peer_indices),
                )

                result = evaluate_value(
                    float(observed),
                    baseline,
                )
                evidence_reason = None

        observed_float = (
            None
            if pd.isna(observed)
            else float(observed)
        )

        transformed = None

        if observed_float is not None:
            if (
                baseline is not None
                and baseline.transformation == "log1p"
            ):
                transformed = float(np.log1p(observed_float))
            else:
                transformed = observed_float

        evidence = {
            "metric_name": metric_name,
            "observed_value": observed_float,
            "decision_method": result["decision_method"],
            "threshold": 3.5,
            "baseline_source": "historical_production_corpus",
        }

        if evidence_reason:
            evidence["reason"] = evidence_reason

        if baseline is not None:
            evidence.update(
                {
                    "peer_group_level": baseline.level,
                    "peer_group_key": baseline.key,
                    "peer_group_size": baseline.size,
                    "peer_median": baseline.median,
                    "peer_mad": baseline.mad,
                    "peer_q1": baseline.q1,
                    "peer_q3": baseline.q3,
                    "transformation": baseline.transformation,
                }
            )

        rows.append(
            {
                "work_id": str(upload_row["work_id"]),
                "metric_name": metric_name,
                "domain": domain,
                "status": result["status"],
                "observed_value": observed_float,
                "transformed_value": transformed,
                "peer_group_level": (
                    baseline.level if baseline is not None else None
                ),
                "peer_group_key": (
                    baseline.key if baseline is not None else None
                ),
                "peer_group_size": (
                    baseline.size if baseline is not None else 0
                ),
                "peer_median": (
                    baseline.median if baseline is not None else None
                ),
                "peer_mad": (
                    baseline.mad if baseline is not None else None
                ),
                "peer_q1": (
                    baseline.q1 if baseline is not None else None
                ),
                "peer_q3": (
                    baseline.q3 if baseline is not None else None
                ),
                "modified_z_score": result["modified_z_score"],
                "lower_bound": result["lower_bound"],
                "upper_bound": result["upper_bound"],
                "direction": result["direction"],
                "decision_method": result["decision_method"],
                "evidence_json": json.dumps(
                    evidence,
                    sort_keys=True,
                    allow_nan=False,
                ),
            }
        )

    return rows


def _build_upload_phase5_outputs(
    upload_features: pd.DataFrame,
    historical_features: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    financial_rows = []

    for metric in FINANCIAL_METRICS:
        financial_rows.extend(
            _score_upload_metric(
                upload_features,
                historical_features,
                metric,
                "FINANCIAL",
            )
        )

    timeline_rows = []

    for metric in TIMELINE_METRICS:
        timeline_rows.extend(
            _score_upload_metric(
                upload_features,
                historical_features,
                metric,
                "TIMELINE",
            )
        )

    anomalies = pd.DataFrame(
        financial_rows + timeline_rows,
        columns=ANOMALY_COLUMNS,
    )

    evaluated = anomalies["status"].isin(
        ["NORMAL", "ANOMALY"]
    )
    anomalous = anomalies["status"].eq("ANOMALY")
    financial = anomalies["domain"].eq("FINANCIAL")
    timeline = anomalies["domain"].eq("TIMELINE")

    indicators = pd.DataFrame(
        {
            "work_id": anomalies["work_id"].to_numpy(copy=False),
            "financial_metrics_evaluated": (
                financial & evaluated
            ).astype("int64"),
            "financial_anomaly_count": (
                financial & anomalous
            ).astype("int64"),
            "timeline_metrics_evaluated": (
                timeline & evaluated
            ).astype("int64"),
            "timeline_anomaly_count": (
                timeline & anomalous
            ).astype("int64"),
            "total_anomaly_count": anomalous.astype("int64"),
            "financial_not_evaluable_count": (
                financial
                & anomalies["status"].eq("NOT_EVALUABLE")
            ).astype("int64"),
            "timeline_not_evaluable_count": (
                timeline
                & anomalies["status"].eq("NOT_EVALUABLE")
            ).astype("int64"),
        }
    )

    summary = (
        indicators
        .groupby("work_id", sort=False, as_index=False)
        .sum()
    )

    evaluated_count = (
        summary["financial_metrics_evaluated"]
        + summary["timeline_metrics_evaluated"]
    )

    summary["phase5_status"] = np.select(
        [
            summary["total_anomaly_count"].gt(0),
            evaluated_count.gt(0),
        ],
        [
            "ANOMALY_FOUND",
            "NO_ANOMALY_FOUND",
        ],
        default="NOT_EVALUABLE",
    )

    return anomalies, summary[SUMMARY_COLUMNS]


# ---------------------------------------------------------------------------
# Phase 6: compare uploads against historical duplicate corpus
# ---------------------------------------------------------------------------

def _build_upload_duplicate_outputs(
    upload_canonical: pd.DataFrame,
    historical_canonical: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    upload_ids = set(
        upload_canonical["work_id"].astype(str)
    )

    # The existing Phase 6 engine intentionally requires canonical
    # production-style Work IDs. Preserve NOT_EVALUABLE for arbitrary
    # user-provided identifiers such as P-001.
    upload_ids_are_canonical = upload_canonical[
        "work_id"
    ].astype(str).map(
        lambda value: bool(
            WORK_ID_PATTERN.fullmatch(value)
        )
    ).all()

    if not upload_ids_are_canonical:
        empty_matches = pd.DataFrame(
            columns=[
                "work_id_a",
                "work_id_b",
                "match_type",
                "similarity_score",
                "description_frequency_a",
                "description_frequency_b",
            ]
        )

        summary = pd.DataFrame(
            {
                "work_id": upload_canonical[
                    "work_id"
                ].astype(str),
                "exact_match_count": 0,
                "similar_match_count": 0,
                "highest_similarity_score": np.nan,
                "phase6_status": "NOT_EVALUABLE",
            }
        )

        return empty_matches, summary

    historical_ids = set(
        historical_canonical["work_id"].astype(str)
    )

    # Avoid ID collisions: an uploaded project with an already-existing
    # production Work ID should not be treated as a separate project.
    overlap = upload_ids.intersection(historical_ids)

    if overlap:
        raise AnalysisInputError(
            "The upload contains Work IDs already present in the "
            "historical corpus: " + ", ".join(sorted(overlap)[:10])
        )

    combined = pd.concat(
        [
            historical_canonical,
            upload_canonical,
        ],
        ignore_index=True,
        sort=False,
    )

    matches, summary = build_phase6_outputs(combined)

    upload_matches = matches[
        matches["work_id_a"].astype(str).isin(upload_ids)
        | matches["work_id_b"].astype(str).isin(upload_ids)
    ].copy()

    upload_summary = summary[
        summary["work_id"].astype(str).isin(upload_ids)
    ].copy()

    return upload_matches, upload_summary


# ---------------------------------------------------------------------------
# Risk input assembly
# ---------------------------------------------------------------------------

def _risk_inputs(
    canonical: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    upload_features = build_ml_features(canonical)

    historical_features = _load_historical_features()
    historical_canonical = _load_historical_canonical()

    # Phase 4 is project-local: evaluate the uploaded project's own data.
    findings, compliance_summary = build_compliance_outputs(
        upload_features
    )

    # Phase 5 is historical-reference based for uploads.
    anomalies, phase5_summary = _build_upload_phase5_outputs(
        upload_features,
        historical_features,
    )

    # Phase 6 compares uploaded descriptions against the historical corpus.
    duplicate_matches, duplicate_summary = (
        _build_upload_duplicate_outputs(
            canonical,
            historical_canonical,
        )
    )

    inputs = {
        "canonical": canonical[["work_id"]],
        "compliance_findings": findings,
        "compliance_summary": compliance_summary,
        "financial_anomalies": anomalies[
            anomalies["domain"].eq("FINANCIAL")
        ],
        "timeline_anomalies": anomalies[
            anomalies["domain"].eq("TIMELINE")
        ],
        "phase5_summary": phase5_summary,
        "duplicate_matches": duplicate_matches,
        "duplicate_summary": duplicate_summary,
    }

    payment_columns = [
        "work_id",
        "sanction_amount",
        "total_expenditure",
        "total_amount_in_progress",
        "n_expenditure_transactions",
        "n_distinct_vendors",
        "n_payment_success",
        "n_payment_in_progress",
        "expenditure_span_days",
    ]

    # Payment AI: TRAIN ONLY ON HISTORICAL DATA.
    # Then score the uploaded projects as unseen rows.
    try:
        payment_model = fit_payment_model(
            historical_features[payment_columns]
        )

        inputs["payment"] = score_payment_data(
            payment_model,
            upload_features[payment_columns],
        )
    except ValueError:
        # If historical payment evidence is insufficient, Risk Fusion
        # will correctly treat Payment AI as unavailable rather than
        # manufacturing a score from the upload itself.
        pass

    # Isolation Forest: TRAIN ONLY ON HISTORICAL DATA.
    # Then score the uploaded projects.
    try:
        isolation_model = fit_isolation_forest_model(
            historical_features
        )

        inputs["isolation_forest"] = (
            score_isolation_forest_data(
                isolation_model,
                upload_features,
            )
        )
    except ValueError:
        # Same principle as Payment AI: unavailable evidence remains
        # unavailable instead of being fitted on the upload.
        pass

    validate_inputs(inputs)

    return inputs


def analyze_csv(
    raw_bytes: bytes,
    filename: str,
) -> dict[str, Any]:
    source = _read_upload(raw_bytes, filename)
    canonical = _canonicalize(source)

    inputs = _risk_inputs(canonical)

    # Reuse the exact Risk Fusion implementation used by production.
    output = build_output(inputs)

    details = (
        canonical
        .set_index("work_id")
        .reindex(output["work_id"])
    )

    projects = []

    for _, row in output.iterrows():
        reasons = []

        if isinstance(row.get("risk_reasons"), str):
            try:
                reasons = json.loads(
                    row["risk_reasons"]
                )
            except json.JSONDecodeError:
                reasons = [row["risk_reasons"]]

        evidence = [
            name
            for name, column in (
                (
                    "compliance",
                    "compliance_contribution",
                ),
                (
                    "financial",
                    "financial_anomaly_contribution",
                ),
                (
                    "timeline",
                    "timeline_anomaly_contribution",
                ),
                (
                    "duplicate",
                    "duplicate_contribution",
                ),
                (
                    "data_quality",
                    "data_quality_contribution",
                ),
                (
                    "payment",
                    "payment_contribution",
                ),
                (
                    "isolation_forest",
                    "isolation_forest_contribution",
                ),
            )
            if float(row.get(column, 0) or 0) > 0
        ]

        source_row = details.loc[row["work_id"]]

        projects.append(
            {
                "work_id": row["work_id"],
                "state": source_row.get("state"),
                "constituency": source_row.get(
                    "constituency"
                ),
                "risk_score": float(
                    row["risk_score"]
                ),
                "risk_level": row["risk_level"],
                "evidence_status": row.get(
                    "evidence_status"
                ),
                "why_risky": reasons,
                "evidence": evidence,
            }
        )

    counts = output["risk_level"].value_counts().to_dict()

    return {
        "status": "success",
        "summary": {
            "total_projects": len(projects),
            "low": int(
                counts.get("LOW", 0)
            ),
            "medium": int(
                counts.get("MEDIUM", 0)
            ),
            "high": int(
                counts.get("HIGH", 0)
            ),
            "critical": int(
                counts.get("CRITICAL", 0)
            ),
        },
        "projects": projects,
    }