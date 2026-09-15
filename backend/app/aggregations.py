"""
Shared aggregation helpers.

This module intentionally supports BOTH aggregation layers used by the app:

1. Canonical ML / Risk Fusion data:
       data/processed/canonical_projects.csv
       data/processed/project_risk_scores.csv

   These are the authoritative sources for current national Dashboard /
   Analytics statistics.

2. Legacy SQLAlchemy Project data:
       Project

   These helpers are retained for legacy/API compatibility and for routes
   that still operate on the application database.

The two layers are kept under distinct function names so their responsibilities
cannot collide.  The legacy SQL helpers also accept either the newer
``query=...`` style or the older ``work_ids=...`` filtering style.

All SQL aggregations are performed in SQL (COUNT/SUM/AVG/MIN/MAX/GROUP BY);
the Project table is never loaded wholesale into Python for aggregation.
"""

from pathlib import Path
from typing import Optional, Sequence

import pandas as pd
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.models import Project
from app.schemas import (
    ByStateStat,
    ByWorkTypeStat,
    StateRiskStat,
    StatusCount,
)


# =====================================================================
# Canonical dataset paths
# =====================================================================

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = BACKEND_ROOT / "data" / "processed"

CANONICAL_PROJECTS_PATH = PROCESSED_DIR / "canonical_projects.csv"
RISK_FUSION_PATH = PROCESSED_DIR / "project_risk_scores.csv"


# =====================================================================
# Canonical dataset loaders
# =====================================================================

def load_canonical_projects() -> pd.DataFrame:
    """Load the current canonical project dataset."""

    if not CANONICAL_PROJECTS_PATH.exists():
        raise FileNotFoundError(
            f"Canonical project dataset not found: {CANONICAL_PROJECTS_PATH}"
        )

    df = pd.read_csv(CANONICAL_PROJECTS_PATH, low_memory=False)

    if "work_id" not in df.columns:
        raise ValueError(
            "canonical_projects.csv does not contain work_id."
        )

    df["work_id"] = df["work_id"].astype(str).str.strip()

    df = df[
        (df["work_id"] != "")
        & (df["work_id"].str.lower() != "nan")
    ].copy()

    df = df.drop_duplicates(subset=["work_id"])

    return df


def load_risk_fusion() -> pd.DataFrame:
    """Load the current Phase 7 Risk Fusion output."""

    if not RISK_FUSION_PATH.exists():
        raise FileNotFoundError(
            f"Risk Fusion output not found: {RISK_FUSION_PATH}"
        )

    df = pd.read_csv(RISK_FUSION_PATH, low_memory=False)

    required = {
        "work_id",
        "risk_score",
        "risk_level",
        "evidence_status",
    }
    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            "Risk Fusion output is missing columns: "
            + ", ".join(sorted(missing))
        )

    df["work_id"] = df["work_id"].astype(str).str.strip()

    df = df[
        (df["work_id"] != "")
        & (df["work_id"].str.lower() != "nan")
    ].copy()

    df = df.drop_duplicates(subset=["work_id"])

    return df


# =====================================================================
# Canonical numeric helper
# =====================================================================

def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    """Convert a canonical numeric column safely to numeric."""

    if column not in df.columns:
        return pd.Series(0.0, index=df.index)

    return pd.to_numeric(df[column], errors="coerce").fillna(0)


# =====================================================================
# Canonical core totals
# =====================================================================

def compute_core_totals_from_canonical(df: pd.DataFrame) -> dict:
    """
    Compute Dashboard totals from the canonical project dataset.

    Available canonical fields include sanction_amount, total_expenditure,
    and status. Financial progress is expenditure / sanction * 100.

    Physical progress and expected completion are unavailable in the
    canonical dataset, so physical progress remains None and delayed-project
    availability is explicitly reported as False.
    """

    total_projects = int(df["work_id"].nunique())

    sanctioned = _numeric(df, "sanction_amount")
    expenditure = _numeric(df, "total_expenditure")

    total_sanctioned_amount = sanctioned.sum()
    total_expenditure = expenditure.sum()

    valid_sanction = sanctioned > 0
    if valid_sanction.any():
        financial_progress = (
            expenditure[valid_sanction]
            / sanctioned[valid_sanction]
            * 100
        )
        average_financial_progress = financial_progress.mean()
    else:
        average_financial_progress = None

    if "status" in df.columns:
        status = (
            df["status"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        )
        completed_projects = int((status == "completed").sum())
    else:
        completed_projects = 0

    active_projects = total_projects - completed_projects

    return {
        "total_projects": total_projects,
        "total_sanctioned_amount": total_sanctioned_amount,
        "total_expenditure": total_expenditure,
        "average_financial_progress": average_financial_progress,
        "average_physical_progress": None,
        "active_projects": active_projects,
        "completed_projects": completed_projects,
        "delayed_projects": 0,
        "delayed_projects_available": False,
        "delayed_projects_reason": (
            "Expected completion data is not available in canonical_projects.csv."
        ),
    }


# =====================================================================
# Canonical state aggregation
# =====================================================================

def compute_by_state_from_canonical(
    df: pd.DataFrame,
) -> list[ByStateStat]:
    """Compute sanctioned amount and expenditure by state."""

    if "state" in df.columns:
        state = (
            df["state"]
            .fillna("Not specified")
            .astype(str)
            .str.strip()
        )
        state = state.replace("", "Not specified")
    else:
        state = pd.Series("Not specified", index=df.index)

    work = df.copy()
    work["_state"] = state
    work["_sanction"] = _numeric(work, "sanction_amount")
    work["_expenditure"] = _numeric(work, "total_expenditure")

    grouped = (
        work.groupby("_state", dropna=False)
        .agg(
            total_sanctioned_amount=("_sanction", "sum"),
            total_expenditure=("_expenditure", "sum"),
        )
        .reset_index()
        .sort_values("total_expenditure", ascending=False)
    )

    return [
        ByStateStat(
            state=str(row["_state"]),
            total_sanctioned_amount=row["total_sanctioned_amount"],
            total_expenditure=row["total_expenditure"],
        )
        for _, row in grouped.iterrows()
    ]


# =====================================================================
# Canonical work type aggregation
# =====================================================================

def compute_by_work_type_from_canonical(
    df: pd.DataFrame,
) -> list[ByWorkTypeStat]:
    """
    Compute project count by work category.

    canonical_projects.csv uses work_category rather than the legacy
    database work_type field.
    """

    if "work_category" in df.columns:
        work_type = (
            df["work_category"]
            .fillna("Not specified")
            .astype(str)
            .str.strip()
        )
        work_type = work_type.replace("", "Not specified")
    else:
        work_type = pd.Series("Not specified", index=df.index)

    grouped = (
        pd.DataFrame({"work_type": work_type})
        .groupby("work_type")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    return [
        ByWorkTypeStat(
            work_type=str(row["work_type"]),
            count=int(row["count"]),
        )
        for _, row in grouped.iterrows()
    ]


# =====================================================================
# Current Risk Fusion aggregations
# =====================================================================

def compute_risk_level_counts_from_risk_fusion(
    risk_df: pd.DataFrame,
) -> dict[str, int]:
    """Compute national risk distribution from current Risk Fusion."""

    levels = (
        risk_df["risk_level"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    counts = levels.value_counts().to_dict()

    return {
        "LOW": int(counts.get("LOW", 0)),
        "MEDIUM": int(counts.get("MEDIUM", 0)),
        "HIGH": int(counts.get("HIGH", 0)),
        "CRITICAL": int(counts.get("CRITICAL", 0)),
    }


def compute_risk_by_state_from_risk_fusion(
    canonical_df: pd.DataFrame,
    risk_df: pd.DataFrame,
) -> list[StateRiskStat]:
    """Combine canonical state metadata with current Risk Fusion levels."""

    if "state" not in canonical_df.columns:
        metadata = canonical_df[["work_id"]].copy()
        metadata["state"] = "Not specified"
    else:
        metadata = canonical_df[["work_id", "state"]].copy()
        metadata["state"] = (
            metadata["state"]
            .fillna("Not specified")
            .astype(str)
            .str.strip()
        )
        metadata.loc[metadata["state"] == "", "state"] = "Not specified"

    metadata["work_id"] = metadata["work_id"].astype(str).str.strip()

    risk = risk_df[["work_id", "risk_level"]].copy()
    risk["work_id"] = risk["work_id"].astype(str).str.strip()
    risk["risk_level"] = (
        risk["risk_level"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    merged = metadata.merge(risk, on="work_id", how="inner")

    result = []
    for state, group in merged.groupby("state", sort=True):
        levels = group["risk_level"]
        result.append(
            StateRiskStat(
                state=str(state),
                low=int((levels == "LOW").sum()),
                medium=int((levels == "MEDIUM").sum()),
                high=int((levels == "HIGH").sum()),
                critical=int((levels == "CRITICAL").sum()),
            )
        )

    return result


# =====================================================================
# Shared label normalization for SQL helpers
# =====================================================================

def _canonical_state_label(value):
    if value is None:
        return "Not specified"
    normalized = str(value).strip()
    return normalized if normalized else "Not specified"


def _canonical_work_type_label(value):
    if value is None:
        return "Not specified"
    normalized = str(value).strip()
    return normalized if normalized else "Not specified"


def _canonical_status_label(value):
    if value is None:
        return "Not specified"
    normalized = str(value).strip()
    if not normalized:
        return "Not specified"
    if normalized.lower() == "not specified":
        return "Not specified"
    return normalized.title()


def _canonical_risk_label(value):
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized.upper()


# =====================================================================
# Legacy SQL filtering compatibility
# =====================================================================

def _query_with_work_ids(
    query,
    work_ids: Optional[Sequence[str]],
):
    """Restrict a SQLAlchemy query to a set of project IDs."""

    if work_ids is None:
        return query

    normalized_ids = [
        str(work_id)
        for work_id in work_ids
        if work_id is not None
    ]

    if not normalized_ids:
        return query.filter(Project.project_id == "__NO_MATCH__")

    return query.filter(Project.project_id.in_(normalized_ids))


def _resolve_base_query(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
):
    """
    Resolve both supported legacy call styles.

    Newer callers can pass:
        compute_x(db, query=my_query)

    Older callers can pass:
        compute_x(db, work_ids)

    Explicit ``work_ids=`` remains supported as well.
    """

    # Backward compatibility: in the old API the second positional argument
    # was work_ids. A SQLAlchemy Query has ``with_entities``; a sequence does
    # not. Strings are treated as a single project ID.
    if query is not None and not hasattr(query, "with_entities"):
        if work_ids is not None:
            raise TypeError(
                "Pass either query or work_ids, not both."
            )
        work_ids = query
        query = None

    base_query = query if query is not None else db.query(Project)
    return _query_with_work_ids(base_query, work_ids)


# =====================================================================
# Legacy SQL core totals
# =====================================================================

def compute_core_totals(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> dict:
    """
    Shared SQL core totals.

    Supports both query-scoped and work-id-scoped callers while preserving
    the original SQL aggregation behavior.
    """

    base_query = _resolve_base_query(db, query, work_ids)

    totals = base_query.with_entities(
        func.count(Project.project_id),
        func.coalesce(func.sum(Project.sanctioned_amount), 0),
        func.coalesce(func.sum(Project.expenditure), 0),
        func.avg(Project.financial_progress),
        func.avg(Project.physical_progress),
    ).one()

    (
        total_projects,
        total_sanctioned_amount,
        total_expenditure,
        average_financial_progress,
        average_physical_progress,
    ) = totals

    completed_projects = (
        base_query.with_entities(func.count(Project.project_id))
        .filter(
            func.lower(func.trim(Project.status)) == "completed"
        )
        .scalar()
    )

    active_projects = total_projects - completed_projects

    delayed_projects = (
        base_query.with_entities(func.count(Project.project_id))
        .filter(
            or_(
                Project.status.is_(None),
                func.lower(func.trim(Project.status)) != "completed",
            ),
            Project.expected_completion.isnot(None),
            Project.expected_completion < func.current_date(),
        )
        .scalar()
    )

    return {
        "total_projects": total_projects,
        "total_sanctioned_amount": total_sanctioned_amount,
        "total_expenditure": total_expenditure,
        "average_financial_progress": average_financial_progress,
        "average_physical_progress": average_physical_progress,
        "active_projects": active_projects,
        "completed_projects": completed_projects,
        "delayed_projects": delayed_projects,
    }


# =====================================================================
# Legacy SQL risk level counts
# =====================================================================

def compute_risk_level_counts(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> dict[str, int]:
    """
    GROUP BY count of Project.risk_level.

    NULL/blank values are ignored; whitespace/case differences are normalized.
    """

    normalized_risk_level = func.lower(func.trim(Project.risk_level))
    base_query = _resolve_base_query(db, query, work_ids)

    rows = (
        base_query.with_entities(
            normalized_risk_level.label("risk_level_key"),
            func.count(Project.project_id),
        )
        .filter(
            func.trim(Project.risk_level).isnot(None),
            func.trim(Project.risk_level) != "",
        )
        .group_by(normalized_risk_level)
        .all()
    )

    return {
        _canonical_risk_label(level): count
        for level, count in rows
        if _canonical_risk_label(level) is not None
    }


# =====================================================================
# Legacy SQL state aggregation
# =====================================================================

def compute_by_state(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> list[ByStateStat]:
    """Sanctioned/expenditure totals grouped by state."""

    state_bucket = func.coalesce(
        func.nullif(func.trim(Project.state), ""),
        "Not specified",
    )
    state_key = func.lower(state_bucket)
    base_query = _resolve_base_query(db, query, work_ids)

    rows = (
        base_query.with_entities(
            state_key.label("state_key"),
            func.max(state_bucket).label("state"),
            func.coalesce(func.sum(Project.sanctioned_amount), 0),
            func.coalesce(func.sum(Project.expenditure), 0),
        )
        .group_by(state_key)
        .order_by(
            desc(func.coalesce(func.sum(Project.expenditure), 0))
        )
        .all()
    )

    return [
        ByStateStat(
            state=_canonical_state_label(state),
            total_sanctioned_amount=sanctioned,
            total_expenditure=expenditure,
        )
        for _, state, sanctioned, expenditure in rows
    ]


# =====================================================================
# Legacy SQL work type aggregation
# =====================================================================

def compute_by_work_type(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> list[ByWorkTypeStat]:
    """Project count grouped by work_type."""

    work_type_bucket = func.coalesce(
        func.nullif(func.trim(Project.work_type), ""),
        "Not specified",
    )
    work_type_key = func.lower(work_type_bucket)
    base_query = _resolve_base_query(db, query, work_ids)

    rows = (
        base_query.with_entities(
            work_type_key.label("work_type_key"),
            func.max(work_type_bucket).label("work_type"),
            func.count(Project.project_id),
        )
        .group_by(work_type_key)
        .order_by(desc(func.count(Project.project_id)))
        .all()
    )

    return [
        ByWorkTypeStat(
            work_type=_canonical_work_type_label(work_type),
            count=count,
        )
        for _, work_type, count in rows
    ]


# =====================================================================
# Legacy SQL risk by state
# =====================================================================

def compute_risk_by_state(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> list[StateRiskStat]:
    """Return LOW/MEDIUM/HIGH/CRITICAL risk counts grouped by state."""

    state_bucket = func.coalesce(
        func.nullif(func.trim(Project.state), ""),
        "Not specified",
    )
    state_key = func.lower(state_bucket)
    base_query = _resolve_base_query(db, query, work_ids)

    rows = (
        base_query.with_entities(
            state_key.label("state_key"),
            func.max(state_bucket).label("state"),
            Project.risk_level,
            func.count(Project.project_id),
        )
        .group_by(
            state_key,
            Project.risk_level,
        )
        .all()
    )

    grouped = {}

    for _, state, level, count in rows:
        canonical_state = _canonical_state_label(state)
        values = grouped.setdefault(
            canonical_state,
            {
                "low": 0,
                "medium": 0,
                "high": 0,
                "critical": 0,
            },
        )

        key = (level or "").strip().lower()
        if key in values:
            values[key] = count

    return [
        StateRiskStat(
            state=state,
            **values,
        )
        for state, values in sorted(grouped.items())
    ]


# =====================================================================
# Legacy SQL status distribution
# =====================================================================

def compute_status_distribution(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> list[StatusCount]:
    """Project count grouped by status."""

    status_bucket = func.coalesce(
        func.nullif(func.trim(Project.status), ""),
        "Not specified",
    )
    status_key = func.lower(status_bucket)
    base_query = _resolve_base_query(db, query, work_ids)

    rows = (
        base_query.with_entities(
            status_key.label("status_key"),
            func.max(status_bucket).label("status"),
            func.count(Project.project_id),
        )
        .group_by(status_key)
        .order_by(desc(func.count(Project.project_id)))
        .all()
    )

    return [
        StatusCount(
            status=_canonical_status_label(status),
            count=count,
        )
        for _, status, count in rows
    ]


# =====================================================================
# Legacy SQL risk score summary
# =====================================================================

def compute_risk_score_summary(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> dict:
    """Average/min/max risk score and count of actually scored projects."""

    base_query = _resolve_base_query(db, query, work_ids)

    average, minimum, maximum, scored_count = base_query.with_entities(
        func.avg(Project.risk_score),
        func.min(Project.risk_score),
        func.max(Project.risk_score),
        func.count(Project.risk_score),
    ).one()

    return {
        "average": average,
        "minimum": minimum,
        "maximum": maximum,
        "scored_project_count": scored_count,
    }


# =====================================================================
# Legacy SQL estimated cost summary
# =====================================================================

def compute_estimated_cost_summary(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> dict:
    """Sum/average/min/max estimated cost and count with available data."""

    base_query = _resolve_base_query(db, query, work_ids)

    total, average, minimum, maximum, count_with_data = (
        base_query.with_entities(
            func.sum(Project.estimated_cost),
            func.avg(Project.estimated_cost),
            func.min(Project.estimated_cost),
            func.max(Project.estimated_cost),
            func.count(Project.estimated_cost),
        ).one()
    )

    return {
        "total": total,
        "average": average,
        "minimum": minimum,
        "maximum": maximum,
        "project_count_with_data": count_with_data,
    }


# =====================================================================
# Legacy SQL progress summary
# =====================================================================

def compute_progress_summary(
    db: Session,
    column,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> dict:
    """Average/min/max and count with data for a progress column."""

    base_query = _resolve_base_query(db, query, work_ids)

    average, minimum, maximum, count_with_data = (
        base_query.with_entities(
            func.avg(column),
            func.min(column),
            func.max(column),
            func.count(column),
        ).one()
    )

    return {
        "average": average,
        "minimum": minimum,
        "maximum": maximum,
        "project_count_with_data": count_with_data,
    }