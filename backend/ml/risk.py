"""Phase 7 — Risk Fusion Engine.

Combines the independent evidence already produced by Phase 4 (compliance),
Phase 5 (financial + timeline anomaly detection), and Phase 6 (duplicate /
similar-work detection) into a single project-level ATTENTION /
INVESTIGATION-PRIORITY score.

This module does not recompute or reinterpret any earlier phase's decisions.
It reads their outputs from ``data/processed/`` as the source of truth,
weighs the evidence they already found, and answers exactly one question per
project: "How much attention does this project require, and why?"

It never claims that fraud has been proven. A high risk_score means "more
independent evidence is present that warrants human review" -- not
"wrongdoing has been established." See ``ml/risk_config.py`` for every
tunable weight/threshold and the reasoning behind each default.

Pipeline (see module docstrings in ml/compliance, ml/anomalies, ml/duplicates
for how each input was produced):

    canonical_projects.csv  (Phase 2 -- master work_id universe)
    compliance_findings.csv, compliance_summary.csv   (Phase 4)
    financial_anomalies.csv, timeline_anomalies.csv,
        phase5_anomaly_summary.csv                    (Phase 5)
    duplicate_matches.csv, duplicate_summary.csv       (Phase 6)
            |
            v
    build_evidence_records()  -> per-category evidence tables
            |
            v
    calculate_contributions() -> capped, pre-overlap per-category points
            |
            v
    handle_overlapping_evidence() -> discount anomaly points that restate
                                      an already-flagged compliance rule
            |
            v
    calculate_risk_score()    -> sum, clipped to [0, 100]
    assign_risk_level()       -> LOW / MEDIUM / HIGH / CRITICAL
    assign_evidence_status()  -> SUFFICIENT / LIMITED / INSUFFICIENT
    generate_reasons()        -> ranked, human-readable explanations
            |
            v
    build_output()            -> one row per canonical work_id
    generate_quality_report() -> distribution / coverage / dominance report
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.config import BACKEND_ROOT
from ml.risk_config import (
    ANOMALY_OVERLAP_DISCOUNT,
    COMPLIANCE_CAP,
    COMPLIANCE_SEVERITY_POINTS,
    DATA_QUALITY_CAP,
    DATA_QUALITY_RULE_POINTS,
    DUPLICATE_CAP,
    DUPLICATE_SIMILARITY_THRESHOLD,
    FINANCIAL_ANOMALY_CAP,
    FINANCIAL_OVERLAP_RULE_IDS,
    TIMELINE_ANOMALY_CAP,
    TIMELINE_OVERLAP_RULE_IDS,
    anomaly_points,
    anomaly_severity_bucket,
    duplicate_rarity_weight,
    evidence_status_for,
    risk_level_for,
)

# --------------------------------------------------------------------------
# Paths -- Phase 7 consumes Phase 2/4/5/6 outputs and writes only its own
# two new files. It never overwrites an earlier phase's output.
# --------------------------------------------------------------------------
PROCESSED_DIR = BACKEND_ROOT / "data" / "processed"
CANONICAL_PATH = PROCESSED_DIR / "canonical_projects.csv"
COMPLIANCE_FINDINGS_PATH = PROCESSED_DIR / "compliance_findings.csv"
COMPLIANCE_SUMMARY_PATH = PROCESSED_DIR / "compliance_summary.csv"
FINANCIAL_ANOMALIES_PATH = PROCESSED_DIR / "financial_anomalies.csv"
TIMELINE_ANOMALIES_PATH = PROCESSED_DIR / "timeline_anomalies.csv"
PHASE5_SUMMARY_PATH = PROCESSED_DIR / "phase5_anomaly_summary.csv"
DUPLICATE_MATCHES_PATH = PROCESSED_DIR / "duplicate_matches.csv"
DUPLICATE_SUMMARY_PATH = PROCESSED_DIR / "duplicate_summary.csv"

RISK_SCORES_OUTPUT_PATH = PROCESSED_DIR / "project_risk_scores.csv"
QUALITY_REPORT_OUTPUT_PATH = PROCESSED_DIR / "risk_quality_report.json"

OUTPUT_COLUMNS = [
    "work_id",
    "risk_score",
    "risk_level",
    "evidence_status",
    "compliance_contribution",
    "financial_anomaly_contribution",
    "timeline_anomaly_contribution",
    "duplicate_contribution",
    "data_quality_contribution",
    "total_evidence_signals",
    "high_severity_signal_count",
    "medium_severity_signal_count",
    "low_severity_signal_count",
    "has_compliance_signal",
    "has_financial_anomaly",
    "has_timeline_anomaly",
    "has_duplicate_signal",
    "has_data_quality_signal",
    "top_reason_1",
    "top_reason_2",
    "top_reason_3",
    "risk_reasons",
    "source_signal_summary",
]

REQUIRED_COMPLIANCE_FINDINGS_COLUMNS = frozenset(
    {"work_id", "rule_id", "category", "status", "severity", "message"}
)
REQUIRED_COMPLIANCE_SUMMARY_COLUMNS = frozenset({"work_id", "compliance_status"})
REQUIRED_ANOMALY_COLUMNS = frozenset(
    {
        "work_id", "metric_name", "domain", "status", "observed_value",
        "peer_group_level", "peer_group_key", "modified_z_score",
        "lower_bound", "upper_bound", "direction", "decision_method",
    }
)
REQUIRED_PHASE5_SUMMARY_COLUMNS = frozenset(
    {"work_id", "financial_metrics_evaluated", "timeline_metrics_evaluated", "phase5_status"}
)
REQUIRED_DUPLICATE_MATCH_COLUMNS = frozenset(
    {
        "work_id_a", "work_id_b", "match_type", "similarity_score",
        "description_frequency_a", "description_frequency_b",
    }
)
REQUIRED_DUPLICATE_SUMMARY_COLUMNS = frozenset(
    {"work_id", "exact_match_count", "similar_match_count", "highest_similarity_score", "phase6_status"}
)

# Human-readable labels for Phase 5 metrics, used only when composing
# risk_reasons text. Purely cosmetic -- never used for scoring.
FINANCIAL_METRIC_LABELS = {
    "recommended_amount": "Recommended amount",
    "sanction_amount": "Sanctioned amount",
    "amount_disbursed": "Amount disbursed",
    "total_expenditure": "Total expenditure",
    "total_amount_in_progress": "Amount in progress",
    "sanction_vs_recommended_ratio": "Sanction-to-recommendation ratio",
    "sanction_minus_recommended_amount": "Sanction-minus-recommendation amount",
    "disbursed_to_sanction_ratio": "Disbursed-to-sanction ratio",
    "expenditure_to_sanction_ratio": "Expenditure-to-sanction ratio",
    "in_progress_amount_to_sanction_ratio": "In-progress-amount-to-sanction ratio",
}
TIMELINE_METRIC_LABELS = {
    "recommendation_to_sanction_days": "Recommendation-to-sanction duration",
    "sanction_to_completion_days": "Sanction-to-completion duration",
    "recommendation_to_completion_days": "Recommendation-to-completion duration",
    "recommendation_to_first_expenditure_days": "Recommendation-to-first-expenditure duration",
    "sanction_to_first_expenditure_days": "Sanction-to-first-expenditure duration",
    "expenditure_span_days": "Expenditure-span duration",
}
AMOUNT_METRICS = frozenset(
    {
        "recommended_amount", "sanction_amount", "amount_disbursed",
        "total_expenditure", "total_amount_in_progress", "sanction_minus_recommended_amount",
    }
)


# ==========================================================================
# 1. load_inputs / validate_inputs
# ==========================================================================

def load_inputs(processed_dir: Path | str = PROCESSED_DIR) -> dict[str, pd.DataFrame]:
    """Load every Phase 2/4/5/6 output Phase 7 needs, as-is.

    Raises FileNotFoundError with a clear message naming the missing phase
    output, rather than a bare pandas error, if an earlier phase has not
    been run yet.
    """
    processed_dir = Path(processed_dir)

    def _read(label: str, filename: str) -> pd.DataFrame:
        path = processed_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"Phase 7 requires {label} at {path}, which does not exist. "
                f"Run the phase that produces it before running Phase 7."
            )
        return pd.read_csv(path)

    return {
        "canonical": _read("the Phase 2 canonical dataset (canonical_projects.csv)", "canonical_projects.csv"),
        "compliance_findings": _read("the Phase 4 compliance findings (compliance_findings.csv)", "compliance_findings.csv"),
        "compliance_summary": _read("the Phase 4 compliance summary (compliance_summary.csv)", "compliance_summary.csv"),
        "financial_anomalies": _read("the Phase 5 financial anomalies (financial_anomalies.csv)", "financial_anomalies.csv"),
        "timeline_anomalies": _read("the Phase 5 timeline anomalies (timeline_anomalies.csv)", "timeline_anomalies.csv"),
        "phase5_summary": _read("the Phase 5 summary (phase5_anomaly_summary.csv)", "phase5_anomaly_summary.csv"),
        "duplicate_matches": _read("the Phase 6 duplicate matches (duplicate_matches.csv)", "duplicate_matches.csv"),
        "duplicate_summary": _read("the Phase 6 duplicate summary (duplicate_summary.csv)", "duplicate_summary.csv"),
    }


def _require_columns(frame: pd.DataFrame, required: frozenset, label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing required Phase 7 columns: {', '.join(missing)}")


def validate_inputs(inputs: dict[str, pd.DataFrame]) -> None:
    """Validate schema and cross-phase Work ID consistency before scoring."""
    canonical = inputs["canonical"]
    if "work_id" not in canonical.columns:
        raise ValueError("canonical_projects.csv is missing the work_id column")
    if canonical["work_id"].isna().any() or not canonical["work_id"].is_unique:
        raise ValueError("canonical_projects.csv must have a non-null, unique work_id column")

    _require_columns(inputs["compliance_findings"], REQUIRED_COMPLIANCE_FINDINGS_COLUMNS, "compliance_findings.csv")
    _require_columns(inputs["compliance_summary"], REQUIRED_COMPLIANCE_SUMMARY_COLUMNS, "compliance_summary.csv")
    _require_columns(inputs["financial_anomalies"], REQUIRED_ANOMALY_COLUMNS, "financial_anomalies.csv")
    _require_columns(inputs["timeline_anomalies"], REQUIRED_ANOMALY_COLUMNS, "timeline_anomalies.csv")
    _require_columns(inputs["phase5_summary"], REQUIRED_PHASE5_SUMMARY_COLUMNS, "phase5_anomaly_summary.csv")
    _require_columns(inputs["duplicate_matches"], REQUIRED_DUPLICATE_MATCH_COLUMNS, "duplicate_matches.csv")
    _require_columns(inputs["duplicate_summary"], REQUIRED_DUPLICATE_SUMMARY_COLUMNS, "duplicate_summary.csv")

    canonical_ids = set(canonical["work_id"].astype(str))
    for name in ("compliance_summary", "phase5_summary", "duplicate_summary"):
        ids = set(inputs[name]["work_id"].astype(str))
        if ids != canonical_ids:
            missing = len(canonical_ids - ids)
            extra = len(ids - canonical_ids)
            raise ValueError(
                f"{name} Work IDs do not match canonical_projects.csv "
                f"({missing} canonical IDs missing from it, {extra} unexpected IDs in it). "
                f"Phase 7 requires every earlier phase to have run on the same canonical dataset."
            )


# ==========================================================================
# 2. build_evidence_records
# ==========================================================================

def _compliance_evidence(findings: pd.DataFrame) -> dict[str, Any]:
    """Aggregate Phase 4 findings into per-work-id compliance evidence.

    DATA_QUALITY findings (DQ01) are deliberately excluded from compliance
    evidence and returned separately -- see risk_config.py's module
    docstring on why data quality is scored under its own capped category.
    """
    findings = findings.copy()
    findings["work_id"] = findings["work_id"].astype(str)

    compliance_flags = findings[(findings["status"] == "FLAG") & (findings["category"] != "DATA_QUALITY")].copy()
    compliance_flags["points"] = compliance_flags["severity"].map(COMPLIANCE_SEVERITY_POINTS).fillna(0.0)

    dq_flags = findings[(findings["status"] == "FLAG") & (findings["category"] == "DATA_QUALITY")].copy()

    points_by_work = compliance_flags.groupby("work_id")["points"].sum()
    high_by_work = compliance_flags[compliance_flags["severity"] == "HIGH"].groupby("work_id").size()
    warning_by_work = compliance_flags[compliance_flags["severity"] == "WARNING"].groupby("work_id").size()
    dq_count_by_work = dq_flags.groupby("work_id").size()

    financial_overlap = set(compliance_flags.loc[compliance_flags["rule_id"].isin(FINANCIAL_OVERLAP_RULE_IDS), "work_id"])
    timeline_overlap = set(compliance_flags.loc[compliance_flags["rule_id"].isin(TIMELINE_OVERLAP_RULE_IDS), "work_id"])

    return {
        "points_by_work": points_by_work,
        "high_by_work": high_by_work,
        "warning_by_work": warning_by_work,
        "dq_count_by_work": dq_count_by_work,
        "financial_overlap_work_ids": financial_overlap,
        "timeline_overlap_work_ids": timeline_overlap,
        "compliance_flags": compliance_flags,
        "dq_flags": dq_flags,
    }


def _anomaly_evidence(anomalies: pd.DataFrame) -> dict[str, Any]:
    """Aggregate one Phase 5 domain (financial or timeline) into evidence.

    Phase 5 does not emit a severity field; anomaly_severity_bucket derives
    a HIGH/MEDIUM/LOW review-priority bucket from the modified z-score
    magnitude purely for Phase 7 weighting (see risk_config.py). This does
    not change Phase 5's own ANOMALY/NORMAL/NOT_EVALUABLE status.
    """
    anomalies = anomalies.copy()
    anomalies["work_id"] = anomalies["work_id"].astype(str)
    anomaly_rows = anomalies[anomalies["status"] == "ANOMALY"].copy()

    if anomaly_rows.empty:
        anomaly_rows["severity_bucket"] = pd.Series(dtype="object")
        anomaly_rows["points"] = pd.Series(dtype="float64")
    else:
        anomaly_rows["severity_bucket"] = [
            anomaly_severity_bucket(z if pd.notna(z) else None, dm)
            for z, dm in zip(anomaly_rows["modified_z_score"], anomaly_rows["decision_method"])
        ]
        anomaly_rows["points"] = [
            anomaly_points(z if pd.notna(z) else None, dm)
            for z, dm in zip(anomaly_rows["modified_z_score"], anomaly_rows["decision_method"])
        ]

    points_by_work = anomaly_rows.groupby("work_id")["points"].sum()
    high_by_work = anomaly_rows[anomaly_rows["severity_bucket"] == "HIGH"].groupby("work_id").size()
    medium_by_work = anomaly_rows[anomaly_rows["severity_bucket"] == "MEDIUM"].groupby("work_id").size()
    low_by_work = anomaly_rows[anomaly_rows["severity_bucket"] == "LOW"].groupby("work_id").size()

    return {
        "points_by_work": points_by_work,
        "high_by_work": high_by_work,
        "medium_by_work": medium_by_work,
        "low_by_work": low_by_work,
        "anomaly_rows": anomaly_rows,
    }


def _duplicate_long_form(matches: pd.DataFrame) -> pd.DataFrame:
    """Expand undirected match pairs into one row per (project, partner).

    Every match in duplicate_matches.csv is stored once, as an unordered
    pair. Risk Fusion needs each project's own view of its matches (its own
    description_frequency, and who it matched with), so each pair
    contributes one row from each side.
    """
    columns = ["work_id", "matched_work_id", "match_type", "similarity_score", "description_frequency"]
    side_a = matches.rename(columns={
        "work_id_a": "work_id", "work_id_b": "matched_work_id", "description_frequency_a": "description_frequency",
    })[columns]
    side_b = matches.rename(columns={
        "work_id_b": "work_id", "work_id_a": "matched_work_id", "description_frequency_b": "description_frequency",
    })[columns]
    long_form = pd.concat([side_a, side_b], ignore_index=True)
    long_form["work_id"] = long_form["work_id"].astype(str)
    long_form["matched_work_id"] = long_form["matched_work_id"].astype(str)
    return long_form


def _duplicate_evidence(matches: pd.DataFrame) -> dict[str, Any]:
    """Aggregate Phase 6 pair evidence into each project's strongest match.

    A project can match many others (especially via common, boilerplate
    descriptions -- see risk_config.py's dominance-check finding), but only
    the single strongest, most-traceable match per match_type is kept for
    scoring and reasons; duplicate_summary.csv already carries the full
    counts for traceability.
    """
    long_form = _duplicate_long_form(matches)

    def _empty_best() -> pd.DataFrame:
        empty = pd.DataFrame({
            "work_id": pd.Series(dtype="object"),
            "matched_work_id": pd.Series(dtype="object"),
            "match_type": pd.Series(dtype="object"),
            "similarity_score": pd.Series(dtype="float64"),
            "description_frequency": pd.Series(dtype="float64"),
        })
        return empty.set_index("work_id")

    exact = long_form[long_form["match_type"] == "EXACT_MATCH"]
    best_exact = (
        exact.sort_values(["description_frequency", "matched_work_id"], kind="mergesort")
        .groupby("work_id", as_index=True)
        .first()
        if not exact.empty else _empty_best()
    )

    similar = long_form[long_form["match_type"] == "SIMILAR_MATCH"]
    best_similar = (
        similar.sort_values(["similarity_score", "description_frequency"], ascending=[False, True], kind="mergesort")
        .groupby("work_id", as_index=True)
        .first()
        if not similar.empty else _empty_best()
    )

    return {"best_exact": best_exact, "best_similar": best_similar}


def build_evidence_records(inputs: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Build every per-category evidence aggregate Phase 7 scores from."""
    return {
        "compliance": _compliance_evidence(inputs["compliance_findings"]),
        "financial": _anomaly_evidence(inputs["financial_anomalies"]),
        "timeline": _anomaly_evidence(inputs["timeline_anomalies"]),
        "duplicate": _duplicate_evidence(inputs["duplicate_matches"]),
    }


# ==========================================================================
# 3. calculate_contributions / handle_overlapping_evidence
# ==========================================================================

def calculate_contributions(evidence: dict[str, Any], work_ids: pd.Index) -> pd.DataFrame:
    """Compute each category's capped, pre-overlap-discount contribution.

    Every contribution is reindexed onto the full canonical work_id universe
    so a project with no evidence in a category gets an explicit 0.0, never
    a missing row.
    """
    contributions = pd.DataFrame(index=work_ids)

    compliance = evidence["compliance"]
    contributions["compliance_raw"] = compliance["points_by_work"].reindex(work_ids).fillna(0.0).clip(upper=COMPLIANCE_CAP)
    contributions["data_quality_raw"] = (
        compliance["dq_count_by_work"].reindex(work_ids).fillna(0).gt(0).astype(float) * DATA_QUALITY_RULE_POINTS
    ).clip(upper=DATA_QUALITY_CAP)

    financial = evidence["financial"]
    contributions["financial_anomaly_raw"] = financial["points_by_work"].reindex(work_ids).fillna(0.0).clip(upper=FINANCIAL_ANOMALY_CAP)

    timeline = evidence["timeline"]
    contributions["timeline_anomaly_raw"] = timeline["points_by_work"].reindex(work_ids).fillna(0.0).clip(upper=TIMELINE_ANOMALY_CAP)

    duplicate = evidence["duplicate"]
    best_exact = duplicate["best_exact"].reindex(work_ids)
    best_similar = duplicate["best_similar"].reindex(work_ids)
    exact_similarity_score = pd.to_numeric(best_exact["similarity_score"], errors="coerce")
    similar_similarity_score = pd.to_numeric(best_similar["similarity_score"], errors="coerce")
    exact_frequency = pd.to_numeric(best_exact["description_frequency"], errors="coerce")
    similar_frequency = pd.to_numeric(best_similar["description_frequency"], errors="coerce")

    has_exact = best_exact["matched_work_id"].notna()
    similar_strength = ((similar_similarity_score - DUPLICATE_SIMILARITY_THRESHOLD) / (1 - DUPLICATE_SIMILARITY_THRESHOLD)).clip(lower=0, upper=1)
    match_strength = pd.Series(np.where(has_exact, 1.0, similar_strength.fillna(0.0)), index=work_ids, dtype="float64")

    rarity_frequency = pd.Series(
        np.where(has_exact, exact_frequency, similar_frequency),
        index=work_ids,
        dtype="float64",
    )
    rarity_weight = rarity_frequency.map(lambda value: duplicate_rarity_weight(value if pd.notna(value) else None)).astype("float64")

    contributions["duplicate_raw"] = (match_strength * rarity_weight * DUPLICATE_CAP).clip(lower=0.0, upper=DUPLICATE_CAP).astype("float64")

    return contributions


def handle_overlapping_evidence(contributions: pd.DataFrame, evidence: dict[str, Any], work_ids: pd.Index) -> pd.DataFrame:
    """Discount anomaly contributions that restate an already-flagged rule.

    See risk_config.py ("2. Compliance point values" / ANOMALY_OVERLAP_DISCOUNT)
    for the exact rationale: C08/C09 (expenditure or disbursement exceeding
    sanction) and C01/C02 (timeline thresholds) are deterministic rule
    breaches over the same underlying quantity a Phase 5 anomaly metric also
    measures statistically. When both fire for the same project, the
    compliance finding is treated as primary evidence and the anomaly
    finding's contribution is halved rather than dropped, so the fused score
    never simply adds two views of one fact at full weight, while still
    reflecting that the anomaly is statistically extreme.
    """
    result = contributions.copy()
    compliance = evidence["compliance"]

    financial_overlap_mask = pd.Series(work_ids.isin(compliance["financial_overlap_work_ids"]), index=work_ids)
    result["financial_anomaly_contribution"] = np.where(
        financial_overlap_mask, result["financial_anomaly_raw"] * ANOMALY_OVERLAP_DISCOUNT, result["financial_anomaly_raw"]
    )
    result["financial_anomaly_contribution"] = result["financial_anomaly_contribution"].clip(lower=0.0, upper=FINANCIAL_ANOMALY_CAP)

    timeline_overlap_mask = pd.Series(work_ids.isin(compliance["timeline_overlap_work_ids"]), index=work_ids)
    result["timeline_anomaly_contribution"] = np.where(
        timeline_overlap_mask, result["timeline_anomaly_raw"] * ANOMALY_OVERLAP_DISCOUNT, result["timeline_anomaly_raw"]
    )
    result["timeline_anomaly_contribution"] = result["timeline_anomaly_contribution"].clip(lower=0.0, upper=TIMELINE_ANOMALY_CAP)

    result["compliance_contribution"] = result["compliance_raw"].clip(lower=0.0, upper=COMPLIANCE_CAP)
    result["data_quality_contribution"] = result["data_quality_raw"].clip(lower=0.0, upper=DATA_QUALITY_CAP)
    result["duplicate_contribution"] = result["duplicate_raw"].clip(lower=0.0, upper=DUPLICATE_CAP)

    result["financial_overlap_applied"] = financial_overlap_mask
    result["timeline_overlap_applied"] = timeline_overlap_mask

    return result[[
        "compliance_contribution", "financial_anomaly_contribution", "timeline_anomaly_contribution",
        "duplicate_contribution", "data_quality_contribution", "financial_overlap_applied", "timeline_overlap_applied",
    ]]


# ==========================================================================
# 4. calculate_risk_score / assign_risk_level / assign_evidence_status
# ==========================================================================

def calculate_risk_score(contributions: pd.DataFrame) -> pd.Series:
    """Sum the five capped, overlap-adjusted contributions and clip to [0, 100]."""
    total = (
        contributions["compliance_contribution"]
        + contributions["financial_anomaly_contribution"]
        + contributions["timeline_anomaly_contribution"]
        + contributions["duplicate_contribution"]
        + contributions["data_quality_contribution"]
    )
    total = total.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return total.clip(lower=0.0, upper=100.0)


def assign_risk_level(risk_score: pd.Series) -> pd.Series:
    return risk_score.map(risk_level_for)


def assign_evidence_status(inputs: dict[str, pd.DataFrame], work_ids: pd.Index) -> pd.DataFrame:
    """Determine, per project, whether each of the 4 evidence domains was
    evaluable, and derive the overall SUFFICIENT/LIMITED/INSUFFICIENT status.

    A domain being "evaluable" means Phase 4-6 had enough valid data to
    actually run a check -- not that the check came back clean. Missing
    data must never read as low risk (Section 11/12 of the Phase 7 brief).
    """
    compliance_summary = inputs["compliance_summary"].copy()
    compliance_summary["work_id"] = compliance_summary["work_id"].astype(str)
    compliance_evaluable = compliance_summary.set_index("work_id")["compliance_status"].reindex(work_ids).ne("NOT_EVALUABLE")

    phase5_summary = inputs["phase5_summary"].copy()
    phase5_summary["work_id"] = phase5_summary["work_id"].astype(str)
    phase5_indexed = phase5_summary.set_index("work_id").reindex(work_ids)
    financial_evaluable = phase5_indexed["financial_metrics_evaluated"].fillna(0).gt(0)
    timeline_evaluable = phase5_indexed["timeline_metrics_evaluated"].fillna(0).gt(0)

    duplicate_summary = inputs["duplicate_summary"].copy()
    duplicate_summary["work_id"] = duplicate_summary["work_id"].astype(str)
    duplicate_evaluable = duplicate_summary.set_index("work_id")["phase6_status"].reindex(work_ids).ne("NOT_EVALUABLE")

    evaluable_count = (
        compliance_evaluable.astype(int)
        + financial_evaluable.astype(int)
        + timeline_evaluable.astype(int)
        + duplicate_evaluable.astype(int)
    )
    evidence_status = evaluable_count.map(evidence_status_for)

    return pd.DataFrame({
        "compliance_evaluable": compliance_evaluable,
        "financial_evaluable": financial_evaluable,
        "timeline_evaluable": timeline_evaluable,
        "duplicate_evaluable": duplicate_evaluable,
        "evaluable_domain_count": evaluable_count,
        "evidence_status": evidence_status,
    }, index=work_ids)


# ==========================================================================
# 5. generate_reasons
# ==========================================================================

def _format_inr(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "an unavailable amount"
    negative = value < 0
    integer_value = int(round(abs(value)))
    digits = str(integer_value)
    if len(digits) > 3:
        last_three = digits[-3:]
        remainder = digits[:-3]
        groups = []
        while len(remainder) > 2:
            groups.insert(0, remainder[-2:])
            remainder = remainder[:-2]
        if remainder:
            groups.insert(0, remainder)
        digits = ",".join(groups) + "," + last_three
    return f"{'-' if negative else ''}\u20b9{digits}"


def _format_metric_value(metric_name: str, value: float | None) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "an unavailable value"
    if metric_name in AMOUNT_METRICS:
        return _format_inr(value)
    if metric_name in TIMELINE_METRIC_LABELS:
        return f"{value:.0f} days"
    return f"{value:.2f}"


def _compliance_reason_rows(compliance_flags: pd.DataFrame) -> pd.DataFrame:
    if compliance_flags.empty:
        return pd.DataFrame(columns=["work_id", "severity_tier", "points", "source_order", "sub_order", "reason_text"])
    rows = compliance_flags.copy()
    rows["severity_tier"] = np.where(rows["severity"] == "HIGH", 3, 2)
    rows["source_order"] = 0
    rows["sub_order"] = rows["rule_id"]
    rows["reason_text"] = rows["message"]
    return rows[["work_id", "severity_tier", "points", "source_order", "sub_order", "reason_text"]]


def _dq_reason_rows(dq_flags: pd.DataFrame) -> pd.DataFrame:
    if dq_flags.empty:
        return pd.DataFrame(columns=["work_id", "severity_tier", "points", "source_order", "sub_order", "reason_text"])
    rows = dq_flags.copy()
    rows["severity_tier"] = 1
    rows["points"] = DATA_QUALITY_RULE_POINTS
    rows["source_order"] = 4
    rows["sub_order"] = rows["rule_id"]
    rows["reason_text"] = rows["message"]
    return rows[["work_id", "severity_tier", "points", "source_order", "sub_order", "reason_text"]]


def _anomaly_reason_rows(anomaly_rows: pd.DataFrame, domain: str, labels: dict[str, str], source_order: int) -> pd.DataFrame:
    if anomaly_rows.empty:
        return pd.DataFrame(columns=["work_id", "severity_tier", "points", "source_order", "sub_order", "reason_text"])
    rows = anomaly_rows.copy()
    tier_map = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    rows["severity_tier"] = rows["severity_bucket"].map(tier_map).fillna(1).astype(int)
    rows["source_order"] = source_order
    rows["sub_order"] = rows["metric_name"]

    def _text(row: pd.Series) -> str:
        label = labels.get(row["metric_name"], row["metric_name"])
        observed = _format_metric_value(row["metric_name"], row["observed_value"] if pd.notna(row["observed_value"]) else None)
        peer_level = row["peer_group_level"] if pd.notna(row["peer_group_level"]) else "the available peer group"
        peer_key = row["peer_group_key"] if pd.notna(row["peer_group_key"]) else "unknown"
        direction = "higher" if row["direction"] == "HIGH" else "lower" if row["direction"] == "LOW" else "different"
        if row["decision_method"] == "modified_z_score" and pd.notna(row["modified_z_score"]):
            return (
                f"{label} of {observed} is unusually {direction} (modified z-score "
                f"{row['modified_z_score']:.2f}) compared with peer projects grouped by "
                f"{peer_level} ('{peer_key}'); this is a statistical review signal, not proof of wrongdoing."
            )
        return (
            f"{label} of {observed} falls outside the normal peer range for projects grouped by "
            f"{peer_level} ('{peer_key}'); this is a statistical review signal, not proof of wrongdoing."
        )

    rows["reason_text"] = rows.apply(_text, axis=1)
    return rows[["work_id", "severity_tier", "points", "source_order", "sub_order", "reason_text"]]


def _duplicate_reason_rows(best_exact: pd.DataFrame, best_similar: pd.DataFrame) -> pd.DataFrame:
    frames = []
    if not best_exact.empty:
        exact = best_exact.reset_index().dropna(subset=["matched_work_id"]).copy()
        if not exact.empty:
            exact["severity_tier"] = 3
            exact["points"] = DUPLICATE_CAP
            exact["source_order"] = 3
            exact["sub_order"] = "EXACT_MATCH"
            exact["reason_text"] = exact.apply(
                lambda row: (
                    f"Work description is an exact normalized match with {row['matched_work_id']} "
                    f"(this description also occurs in {int(row['description_frequency'])} project description(s) "
                    f"in the dataset); this is a potential similar-work / duplicate review candidate, "
                    f"not a confirmed duplicate."
                ),
                axis=1,
            )
            frames.append(exact[["work_id", "severity_tier", "points", "source_order", "sub_order", "reason_text"]])
    if not best_similar.empty:
        similar = best_similar.reset_index().dropna(subset=["matched_work_id"]).copy()
        if not similar.empty:
            similar["severity_tier"] = np.where(similar["similarity_score"] >= 0.95, 2, 1)
            similar["points"] = ((similar["similarity_score"] - DUPLICATE_SIMILARITY_THRESHOLD) / (1 - DUPLICATE_SIMILARITY_THRESHOLD)).clip(lower=0, upper=1) * DUPLICATE_CAP
            similar["source_order"] = 3
            similar["sub_order"] = "SIMILAR_MATCH"
            similar["reason_text"] = similar.apply(
                lambda row: (
                    f"Work description has a {row['similarity_score'] * 100:.0f}% similarity match with "
                    f"{row['matched_work_id']} (this description also occurs in "
                    f"{int(row['description_frequency'])} project description(s) in the dataset); this is a "
                    f"potential similar-work review candidate requiring manual review, not a confirmed duplicate."
                ),
                axis=1,
            )
            frames.append(similar[["work_id", "severity_tier", "points", "source_order", "sub_order", "reason_text"]])
    if not frames:
        return pd.DataFrame(columns=["work_id", "severity_tier", "points", "source_order", "sub_order", "reason_text"])
    return pd.concat(frames, ignore_index=True)


def generate_reasons(evidence: dict[str, Any], work_ids: pd.Index) -> pd.DataFrame:
    """Build ranked, human-readable reasons and a source_signal_summary per project.

    Ranking is deterministic: severity tier (HIGH=3/MEDIUM=2/LOW=1) first,
    then points, then a fixed source order, then a stable sub-key -- never
    row position or randomness (Section 23).
    """
    compliance = evidence["compliance"]
    financial = evidence["financial"]
    timeline = evidence["timeline"]
    duplicate = evidence["duplicate"]

    reason_rows = pd.concat(
        [
            _compliance_reason_rows(compliance["compliance_flags"]),
            _anomaly_reason_rows(financial["anomaly_rows"], "financial", FINANCIAL_METRIC_LABELS, source_order=1),
            _anomaly_reason_rows(timeline["anomaly_rows"], "timeline", TIMELINE_METRIC_LABELS, source_order=2),
            _duplicate_reason_rows(duplicate["best_exact"], duplicate["best_similar"]),
            _dq_reason_rows(compliance["dq_flags"]),
        ],
        ignore_index=True,
    )

    top_reasons = {work_id: ["", "", ""] for work_id in work_ids}
    all_reasons: dict[str, list[str]] = {work_id: [] for work_id in work_ids}
    summaries: dict[str, list[dict[str, Any]]] = {work_id: [] for work_id in work_ids}

    if not reason_rows.empty:
        reason_rows = reason_rows.sort_values(
            ["work_id", "severity_tier", "points", "source_order", "sub_order"],
            ascending=[True, False, False, True, True],
            kind="mergesort",
        )
        for work_id, group in reason_rows.groupby("work_id", sort=False):
            texts = group["reason_text"].tolist()
            all_reasons[work_id] = texts
            padded = (texts + ["", "", ""])[:3]
            top_reasons[work_id] = padded
            summaries[work_id] = group[["source_order", "sub_order", "severity_tier", "points"]].to_dict("records")

    source_names = {0: "compliance", 1: "financial_anomaly", 2: "timeline_anomaly", 3: "duplicate", 4: "data_quality"}

    result = pd.DataFrame(index=work_ids)
    result["top_reason_1"] = [top_reasons[w][0] or None for w in work_ids]
    result["top_reason_2"] = [top_reasons[w][1] or None for w in work_ids]
    result["top_reason_3"] = [top_reasons[w][2] or None for w in work_ids]
    result["risk_reasons"] = [json.dumps(all_reasons[w], ensure_ascii=False) for w in work_ids]
    result["source_signal_summary"] = [
        json.dumps(
            {
                "signals": [
                    {
                        "source": source_names[record["source_order"]],
                        "identifier": record["sub_order"],
                        "severity_tier": record["severity_tier"],
                        "points": round(float(record["points"]), 4),
                    }
                    for record in summaries[w]
                ]
            },
            sort_keys=True,
            allow_nan=False,
        )
        for w in work_ids
    ]
    return result


# ==========================================================================
# 6. build_output
# ==========================================================================

def build_output(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Run the full Phase 7 pipeline and return exactly one row per Work ID."""
    canonical = inputs["canonical"].copy()
    canonical["work_id"] = canonical["work_id"].astype(str)
    work_ids = pd.Index(sorted(canonical["work_id"].unique()), name="work_id")

    evidence = build_evidence_records(inputs)
    contributions = calculate_contributions(evidence, work_ids)
    contributions = handle_overlapping_evidence(contributions, evidence, work_ids)

    risk_score = calculate_risk_score(contributions)
    risk_level = assign_risk_level(risk_score)
    evidence_status_frame = assign_evidence_status(inputs, work_ids)
    reasons = generate_reasons(evidence, work_ids)

    compliance = evidence["compliance"]
    financial = evidence["financial"]
    timeline = evidence["timeline"]
    duplicate = evidence["duplicate"]

    high_compliance = compliance["high_by_work"].reindex(work_ids).fillna(0)
    warning_compliance = compliance["warning_by_work"].reindex(work_ids).fillna(0)
    dq_count = compliance["dq_count_by_work"].reindex(work_ids).fillna(0)
    financial_high = financial["high_by_work"].reindex(work_ids).fillna(0)
    financial_medium = financial["medium_by_work"].reindex(work_ids).fillna(0)
    financial_low = financial["low_by_work"].reindex(work_ids).fillna(0)
    timeline_high = timeline["high_by_work"].reindex(work_ids).fillna(0)
    timeline_medium = timeline["medium_by_work"].reindex(work_ids).fillna(0)
    timeline_low = timeline["low_by_work"].reindex(work_ids).fillna(0)

    duplicate_summary = inputs["duplicate_summary"].copy()
    duplicate_summary["work_id"] = duplicate_summary["work_id"].astype(str)
    duplicate_summary_indexed = duplicate_summary.set_index("work_id").reindex(work_ids)
    exact_match_count = duplicate_summary_indexed["exact_match_count"].fillna(0)
    similar_match_count = duplicate_summary_indexed["similar_match_count"].fillna(0)
    highest_similarity = duplicate_summary_indexed["highest_similarity_score"]
    duplicate_high = exact_match_count.gt(0).astype(int)
    duplicate_medium = (exact_match_count.eq(0) & similar_match_count.gt(0) & highest_similarity.fillna(0).ge(0.95)).astype(int)
    duplicate_low = (exact_match_count.eq(0) & similar_match_count.gt(0) & highest_similarity.fillna(0).lt(0.95)).astype(int)

    high_severity_signal_count = high_compliance + financial_high + timeline_high + duplicate_high
    medium_severity_signal_count = warning_compliance + financial_medium + timeline_medium + duplicate_medium
    low_severity_signal_count = financial_low + timeline_low + duplicate_low + dq_count.gt(0).astype(int)
    total_evidence_signals = high_severity_signal_count + medium_severity_signal_count + low_severity_signal_count

    output = pd.DataFrame(index=work_ids)
    output["work_id"] = work_ids
    output["risk_score"] = risk_score.round(2).to_numpy()
    output["risk_level"] = risk_level.to_numpy()
    output["evidence_status"] = evidence_status_frame["evidence_status"].to_numpy()
    output["compliance_contribution"] = contributions["compliance_contribution"].round(2).to_numpy()
    output["financial_anomaly_contribution"] = contributions["financial_anomaly_contribution"].round(2).to_numpy()
    output["timeline_anomaly_contribution"] = contributions["timeline_anomaly_contribution"].round(2).to_numpy()
    output["duplicate_contribution"] = contributions["duplicate_contribution"].round(2).to_numpy()
    output["data_quality_contribution"] = contributions["data_quality_contribution"].round(2).to_numpy()
    output["total_evidence_signals"] = total_evidence_signals.astype(int).to_numpy()
    output["high_severity_signal_count"] = high_severity_signal_count.astype(int).to_numpy()
    output["medium_severity_signal_count"] = medium_severity_signal_count.astype(int).to_numpy()
    output["low_severity_signal_count"] = low_severity_signal_count.astype(int).to_numpy()
    output["has_compliance_signal"] = (high_compliance + warning_compliance).gt(0).to_numpy()
    output["has_financial_anomaly"] = (financial_high + financial_medium + financial_low).gt(0).to_numpy()
    output["has_timeline_anomaly"] = (timeline_high + timeline_medium + timeline_low).gt(0).to_numpy()
    output["has_duplicate_signal"] = (exact_match_count + similar_match_count).gt(0).to_numpy()
    output["has_data_quality_signal"] = dq_count.gt(0).to_numpy()
    output["top_reason_1"] = reasons["top_reason_1"].to_numpy()
    output["top_reason_2"] = reasons["top_reason_2"].to_numpy()
    output["top_reason_3"] = reasons["top_reason_3"].to_numpy()
    output["risk_reasons"] = reasons["risk_reasons"].to_numpy()
    output["source_signal_summary"] = reasons["source_signal_summary"].to_numpy()

    output = output.reset_index(drop=True)

    if output["work_id"].isna().any() or not output["work_id"].is_unique:
        raise RuntimeError("Phase 7 output must have exactly one row per non-null Work ID")
    if not output["risk_score"].between(0, 100).all():
        raise RuntimeError("Phase 7 produced a risk_score outside the valid 0-100 range")
    if output["risk_score"].isna().any() or np.isinf(output["risk_score"].to_numpy()).any():
        raise RuntimeError("Phase 7 produced a NaN or infinite risk_score")

    return output[OUTPUT_COLUMNS]


def write_risk_outputs(
    output: pd.DataFrame,
    quality_report: dict[str, Any],
    output_dir: Path | str = PROCESSED_DIR,
) -> tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    scores_path = output_dir / "project_risk_scores.csv"
    report_path = output_dir / "risk_quality_report.json"
    output.to_csv(scores_path, index=False)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(quality_report, handle, indent=2, sort_keys=True, allow_nan=False)
    return scores_path, report_path


# ==========================================================================
# 7. generate_quality_report
# ==========================================================================

def _distribution(series: pd.Series) -> dict[str, float]:
    if series.empty:
        return {"count": 0}
    percentiles = series.quantile([0.25, 0.5, 0.75, 0.9, 0.95, 0.99])
    return {
        "count": int(series.count()),
        "min": float(series.min()),
        "max": float(series.max()),
        "mean": float(series.mean()),
        "median": float(series.median()),
        "p25": float(percentiles.loc[0.25]),
        "p50": float(percentiles.loc[0.5]),
        "p75": float(percentiles.loc[0.75]),
        "p90": float(percentiles.loc[0.9]),
        "p95": float(percentiles.loc[0.95]),
        "p99": float(percentiles.loc[0.99]),
    }


def generate_quality_report(output: pd.DataFrame) -> dict[str, Any]:
    """Build the Phase 7 quality report: distribution, coverage, dominance."""
    total_projects = len(output)
    contribution_columns = [
        "compliance_contribution", "financial_anomaly_contribution", "timeline_anomaly_contribution",
        "duplicate_contribution", "data_quality_contribution",
    ]
    contributions = output[contribution_columns]
    largest_contributor = contributions.idxmax(axis=1)
    has_any_contribution = contributions.sum(axis=1).gt(0)

    dominant_share = {}
    for column in contribution_columns:
        is_largest_and_positive = (largest_contributor == column) & has_any_contribution
        dominant_share[column] = {
            "mean_contribution": float(contributions[column].mean()) if total_projects else 0.0,
            "median_contribution": float(contributions[column].median()) if total_projects else 0.0,
            "pct_projects_where_largest_contributor": (
                round(100.0 * is_largest_and_positive.sum() / total_projects, 2) if total_projects else 0.0
            ),
        }

    return {
        "total_projects": total_projects,
        "risk_level_counts": output["risk_level"].value_counts().to_dict(),
        "evidence_status_counts": output["evidence_status"].value_counts().to_dict(),
        "risk_score_distribution": _distribution(output["risk_score"]),
        "zero_signal_project_count": int(output["total_evidence_signals"].eq(0).sum()),
        "insufficient_evidence_project_count": int(output["evidence_status"].eq("INSUFFICIENT").sum()),
        "reason_coverage": {
            "projects_with_top_reason_1": int(output["top_reason_1"].notna().sum()),
            "projects_with_all_three_reasons": int(output["top_reason_3"].notna().sum()),
            "projects_with_zero_signals_and_no_reason": int(
                (output["total_evidence_signals"].eq(0) & output["top_reason_1"].isna()).sum()
            ),
        },
        "evidence_coverage": {
            "projects_with_compliance_evidence": int(output["has_compliance_signal"].sum()),
            "projects_with_financial_anomaly_evidence": int(output["has_financial_anomaly"].sum()),
            "projects_with_timeline_anomaly_evidence": int(output["has_timeline_anomaly"].sum()),
            "projects_with_duplicate_evidence": int(output["has_duplicate_signal"].sum()),
            "projects_with_data_quality_evidence": int(output["has_data_quality_signal"].sum()),
            "projects_with_multiple_evidence_categories": int(
                (
                    output["has_compliance_signal"].astype(int)
                    + output["has_financial_anomaly"].astype(int)
                    + output["has_timeline_anomaly"].astype(int)
                    + output["has_duplicate_signal"].astype(int)
                    + output["has_data_quality_signal"].astype(int)
                ).ge(2).sum()
            ),
        },
        "contribution_distributions": {
            column: _distribution(output[column]) for column in contribution_columns
        },
        "dominance_check": dominant_share,
        "traceability_coverage": {
            "projects_with_source_signal_summary": int(
                output["source_signal_summary"].map(lambda value: json.loads(value)["signals"] != []).sum()
            ),
        },
        "configuration": {
            "evidence_category_caps": {
                "compliance": COMPLIANCE_CAP,
                "financial_anomaly": FINANCIAL_ANOMALY_CAP,
                "timeline_anomaly": TIMELINE_ANOMALY_CAP,
                "duplicate": DUPLICATE_CAP,
                "data_quality": DATA_QUALITY_CAP,
            },
            "compliance_severity_points": COMPLIANCE_SEVERITY_POINTS,
            "data_quality_rule_points": DATA_QUALITY_RULE_POINTS,
            "anomaly_overlap_discount": ANOMALY_OVERLAP_DISCOUNT,
            "financial_overlap_rule_ids": sorted(FINANCIAL_OVERLAP_RULE_IDS),
            "timeline_overlap_rule_ids": sorted(TIMELINE_OVERLAP_RULE_IDS),
            "duplicate_similarity_threshold": DUPLICATE_SIMILARITY_THRESHOLD,
            "risk_level_thresholds": "LOW < 25, 25 <= MEDIUM < 50, 50 <= HIGH < 75, CRITICAL >= 75",
            "evidence_status_thresholds": "0 evaluable domains = INSUFFICIENT, 1-2 = LIMITED, 3-4 = SUFFICIENT",
        },
    }


# ==========================================================================
# Entrypoint
# ==========================================================================

def run_phase7(processed_dir: Path | str = PROCESSED_DIR) -> tuple[pd.DataFrame, dict[str, Any]]:
    inputs = load_inputs(processed_dir)
    validate_inputs(inputs)
    output = build_output(inputs)
    quality_report = generate_quality_report(output)
    return output, quality_report


def main() -> None:
    output, quality_report = run_phase7()
    scores_path, report_path = write_risk_outputs(output, quality_report)
    print(f"Phase 7 risk scores written: {len(output):,} rows x {len(output.columns)} columns")
    print(scores_path)
    print(report_path)
    print(f"Risk level counts: {quality_report['risk_level_counts']}")
    print(f"Evidence status counts: {quality_report['evidence_status_counts']}")


if __name__ == "__main__":
    main()