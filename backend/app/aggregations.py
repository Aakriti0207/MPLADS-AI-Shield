"""
Shared aggregation helpers.

There are two data sources in the application:

1. Canonical ML dataset:
       data/processed/canonical_projects.csv

   This is the authoritative 43,863-project project universe used by
   the current ML/Risk Fusion pipeline.

2. Project database:
       Project

   This remains available for legacy/API compatibility and for
   authenticated application data.

Dashboard/Analytics should prefer the canonical dataset for national
project statistics so that totals are consistent with the current
Risk Fusion universe.
"""

from pathlib import Path
from typing import Any, Optional, Sequence

import pandas as pd

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models import Project
from app.schemas import (
    ByStateStat,
    ByWorkTypeStat,
    StateRiskStat,
    StatusCount,
)


# =====================================================================
# Paths
# =====================================================================

BACKEND_ROOT = Path(__file__).resolve().parents[1]

PROCESSED_DIR = BACKEND_ROOT / "data" / "processed"

CANONICAL_PROJECTS_PATH = (
    PROCESSED_DIR / "canonical_projects.csv"
)

RISK_FUSION_PATH = (
    PROCESSED_DIR / "project_risk_scores.csv"
)


# =====================================================================
# Canonical dataset loader
# =====================================================================

def load_canonical_projects() -> pd.DataFrame:
    """
    Load the current canonical project dataset.

    This should contain the same 43,863-project universe used by the
    current ML pipeline.
    """

    if not CANONICAL_PROJECTS_PATH.exists():
        raise FileNotFoundError(
            f"Canonical project dataset not found: "
            f"{CANONICAL_PROJECTS_PATH}"
        )

    df = pd.read_csv(
        CANONICAL_PROJECTS_PATH,
        low_memory=False,
    )

    if "work_id" not in df.columns:
        raise ValueError(
            "canonical_projects.csv does not contain work_id."
        )

    df["work_id"] = (
        df["work_id"]
        .astype(str)
        .str.strip()
    )

    df = df[
        (df["work_id"] != "")
        & (df["work_id"].str.lower() != "nan")
    ].copy()

    df = df.drop_duplicates(
        subset=["work_id"]
    )

    return df


# =====================================================================
# Risk Fusion loader
# =====================================================================

def load_risk_fusion() -> pd.DataFrame:
    """
    Load the current Phase 7 Risk Fusion output.
    """

    if not RISK_FUSION_PATH.exists():
        raise FileNotFoundError(
            f"Risk Fusion output not found: "
            f"{RISK_FUSION_PATH}"
        )

    df = pd.read_csv(
        RISK_FUSION_PATH,
        low_memory=False,
    )

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

    df["work_id"] = (
        df["work_id"]
        .astype(str)
        .str.strip()
    )

    df = df[
        (df["work_id"] != "")
        & (df["work_id"].str.lower() != "nan")
    ].copy()

    df = df.drop_duplicates(
        subset=["work_id"]
    )

    return df


# =====================================================================
# Canonical numeric helper
# =====================================================================

def _numeric(
    df: pd.DataFrame,
    column: str,
) -> pd.Series:
    """
    Convert a canonical numeric column safely to numeric.
    """

    if column not in df.columns:
        return pd.Series(
            0.0,
            index=df.index,
        )

    return pd.to_numeric(
        df[column],
        errors="coerce",
    ).fillna(0)


# =====================================================================
# Canonical core totals
# =====================================================================

def compute_core_totals_from_canonical(
    df: pd.DataFrame,
) -> dict:
    """
    Compute Dashboard totals from the canonical 43,863-project
    dataset.

    Available canonical fields include:

        sanction_amount
        total_expenditure
        status

    Financial progress is calculated as:

        total_expenditure / sanction_amount * 100

    Physical progress and expected completion are unavailable in the
    canonical dataset, so they remain None.
    """

    total_projects = int(
        df["work_id"].nunique()
    )

    sanctioned = _numeric(
        df,
        "sanction_amount",
    )

    expenditure = _numeric(
        df,
        "total_expenditure",
    )

    total_sanctioned_amount = (
        sanctioned.sum()
    )

    total_expenditure = (
        expenditure.sum()
    )

    # ---------------------------------------------------------------
    # Financial progress
    # ---------------------------------------------------------------

    valid_sanction = sanctioned > 0

    if valid_sanction.any():

        financial_progress = (
            expenditure[valid_sanction]
            / sanctioned[valid_sanction]
            * 100
        )

        average_financial_progress = (
            financial_progress.mean()
        )

    else:
        average_financial_progress = None

    # ---------------------------------------------------------------
    # Status
    # ---------------------------------------------------------------

    if "status" in df.columns:

        status = (
            df["status"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        )

        completed_mask = (
            status == "completed"
        )

        completed_projects = int(
            completed_mask.sum()
        )

    else:

        completed_projects = 0

    active_projects = (
        total_projects
        - completed_projects
    )

    # ---------------------------------------------------------------
    # Expected completion / physical progress
    #
    # These fields are not present in canonical_projects.csv.
    # ---------------------------------------------------------------

    delayed_projects = 0

    return {
        "total_projects": total_projects,

        "total_sanctioned_amount": (
            total_sanctioned_amount
        ),

        "total_expenditure": (
            total_expenditure
        ),

        "average_financial_progress": (
            average_financial_progress
        ),

        "average_physical_progress": None,

        "active_projects": active_projects,

        "completed_projects": completed_projects,

        "delayed_projects": delayed_projects,

        "delayed_projects_available": False,

        "delayed_projects_reason": (
            "Expected completion data is not "
            "available in canonical_projects.csv."
        ),
    }


# =====================================================================
# Canonical state aggregation
# =====================================================================

def compute_by_state_from_canonical(
    df: pd.DataFrame,
) -> list[ByStateStat]:
    """
    Compute sanctioned amount and expenditure by state from the
    canonical dataset.
    """

    if "state" in df.columns:

        state = (
            df["state"]
            .fillna("Not specified")
            .astype(str)
            .str.strip()
        )

        state = state.replace(
            "",
            "Not specified",
        )

    else:

        state = pd.Series(
            "Not specified",
            index=df.index,
        )

    work = df.copy()

    work["_state"] = state

    work["_sanction"] = _numeric(
        work,
        "sanction_amount",
    )

    work["_expenditure"] = _numeric(
        work,
        "total_expenditure",
    )

    grouped = (
        work
        .groupby("_state", dropna=False)
        .agg(
            total_sanctioned_amount=(
                "_sanction",
                "sum",
            ),
            total_expenditure=(
                "_expenditure",
                "sum",
            ),
        )
        .reset_index()
    )

    grouped = grouped.sort_values(
        "total_expenditure",
        ascending=False,
    )

    return [
        ByStateStat(
            state=str(row["_state"]),
            total_sanctioned_amount=(
                row["total_sanctioned_amount"]
            ),
            total_expenditure=(
                row["total_expenditure"]
            ),
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

        work_type = work_type.replace(
            "",
            "Not specified",
        )

    else:

        work_type = pd.Series(
            "Not specified",
            index=df.index,
        )

    grouped = (
        pd.DataFrame(
            {
                "work_type": work_type,
            }
        )
        .groupby("work_type")
        .size()
        .reset_index(name="count")
        .sort_values(
            "count",
            ascending=False,
        )
    )

    return [
        ByWorkTypeStat(
            work_type=str(row["work_type"]),
            count=int(row["count"]),
        )
        for _, row in grouped.iterrows()
    ]


# =====================================================================
# Current Risk Fusion level counts
# =====================================================================

def _none_if_blank_value(value):
    """Return None for missing/blank values, otherwise a stripped string."""
    if value is None or pd.isna(value):
        return None

    value = str(value).strip()

    return value


def compute_status_distribution_from_canonical(
    canonical_df: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Return project counts grouped by canonical lifecycle status.

    NULL/blank status is represented explicitly as ``Not specified``.
    """
    if "status" not in canonical_df.columns:
        return []

    status = (
        canonical_df["status"]
        .fillna("Not specified")
        .astype(str)
        .str.strip()
        .replace("", "Not specified")
    )

    counts = status.value_counts().sort_values(ascending=False)

    return [
        {
            "status": str(name),
            "count": int(count),
        }
        for name, count in counts.items()
    ]


def compute_recent_projects_from_canonical(
    canonical_df: pd.DataFrame,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Return recently active projects using real canonical dates.

    ``last_expenditure_date`` is preferred because it represents actual
    project activity. Projects without that date are ordered after projects
    with activity. No dates are fabricated.
    """
    if canonical_df.empty or limit <= 0:
        return []

    df = canonical_df.copy()

    date_columns = [
        "last_expenditure_date",
        "completion_date",
        "sanction_date",
    ]

    for column in date_columns:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce")

    if "last_expenditure_date" in df.columns:
        sort_date = df["last_expenditure_date"]
    elif "completion_date" in df.columns:
        sort_date = df["completion_date"]
    elif "sanction_date" in df.columns:
        sort_date = df["sanction_date"]
    else:
        return []

    df["_recent_date"] = sort_date

    df = (
        df.sort_values(
            by=["_recent_date", "work_id"],
            ascending=[False, True],
            na_position="last",
        )
        .head(limit)
    )

    results = []

    for _, row in df.iterrows():
        def _date_value(column):
            value = row.get(column)
            if pd.isna(value):
                return None
            return value.date()

        sanction_amount = pd.to_numeric(
            row.get("sanction_amount"),
            errors="coerce",
        )
        expenditure = pd.to_numeric(
            row.get("total_expenditure"),
            errors="coerce",
        )

        financial_progress = None
        if pd.notna(sanction_amount) and sanction_amount > 0 and pd.notna(expenditure):
            financial_progress = float(
                expenditure / sanction_amount * 100
            )

        results.append(
            {
                "project_id": str(row.get("work_id")),
                "state": _none_if_blank_value(row.get("state")),
                "district": _none_if_blank_value(row.get("district")),
                "constituency": _none_if_blank_value(row.get("constituency")),
                "mp_name": _none_if_blank_value(row.get("mp")),
                "work_type": _none_if_blank_value(row.get("work_category")),
                "implementing_agency": _none_if_blank_value(
                    row.get("implementing_agency")
                ),
                "sanctioned_amount": (
                    float(sanction_amount)
                    if pd.notna(sanction_amount)
                    else None
                ),
                "expenditure": (
                    float(expenditure)
                    if pd.notna(expenditure)
                    else None
                ),
                "financial_progress": financial_progress,
                "status": _none_if_blank_value(row.get("status")),
                "sanction_date": _date_value("sanction_date"),
                "start_date": _date_value("sanction_date"),
                "expected_completion": None,
                "actual_completion": _date_value("completion_date"),
            }
        )

    return results


def compute_risk_level_counts_from_risk_fusion(
    risk_df: pd.DataFrame,
) -> dict[str, int]:
    """
    Compute national risk distribution from current Risk Fusion.
    """

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


# =====================================================================
# Current Risk Fusion risk by state
# =====================================================================

def compute_risk_by_state_from_risk_fusion(
    canonical_df: pd.DataFrame,
    risk_df: pd.DataFrame,
) -> list[StateRiskStat]:
    """
    Combine canonical state metadata with current Risk Fusion risk
    levels.
    """

    metadata = canonical_df[
        [
            "work_id",
            "state",
        ]
    ].copy()

    metadata["work_id"] = (
        metadata["work_id"]
        .astype(str)
        .str.strip()
    )

    metadata["state"] = (
        metadata["state"]
        .fillna("Not specified")
        .astype(str)
        .str.strip()
    )

    metadata.loc[
        metadata["state"] == "",
        "state",
    ] = "Not specified"

    risk = risk_df[
        [
            "work_id",
            "risk_level",
        ]
    ].copy()

    risk["work_id"] = (
        risk["work_id"]
        .astype(str)
        .str.strip()
    )

    risk["risk_level"] = (
        risk["risk_level"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    merged = metadata.merge(
        risk,
        on="work_id",
        how="inner",
    )

    result = []

    for state, group in merged.groupby(
        "state",
        sort=True,
    ):

        levels = group["risk_level"]

        result.append(
            StateRiskStat(
                state=str(state),
                low=int(
                    (levels == "LOW").sum()
                ),
                medium=int(
                    (levels == "MEDIUM").sum()
                ),
                high=int(
                    (levels == "HIGH").sum()
                ),
                critical=int(
                    (levels == "CRITICAL").sum()
                ),
            )
        )

    return result


# =====================================================================
# Legacy SQL helpers
#
# These are retained so existing Analytics/other routes do not break.
# New Dashboard code should use the canonical helpers above.
# =====================================================================

def _query_with_work_ids(
    query,
    work_ids: Optional[Sequence[str]],
):
    """
    Optionally restrict a SQLAlchemy query to a set of project IDs.
    """

    if work_ids is None:
        return query

    normalized_ids = [
        str(work_id)
        for work_id in work_ids
        if work_id is not None
    ]

    if not normalized_ids:
        return query.filter(
            Project.project_id == "__NO_MATCH__"
        )

    return query.filter(
        Project.project_id.in_(normalized_ids)
    )


def compute_core_totals(
    db: Session,
    work_ids: Optional[Sequence[str]] = None,
) -> dict:
    """
    Legacy SQL-based core totals.

    Retained for compatibility.
    """

    base_query = _query_with_work_ids(
        db.query(Project),
        work_ids,
    )

    row = (
        base_query
        .with_entities(
            func.count(Project.project_id),
            func.coalesce(
                func.sum(Project.sanctioned_amount),
                0,
            ),
            func.coalesce(
                func.sum(Project.expenditure),
                0,
            ),
            func.avg(
                Project.financial_progress
            ),
            func.avg(
                Project.physical_progress
            ),
        )
        .one()
    )

    (
        total_projects,
        total_sanctioned_amount,
        total_expenditure,
        average_financial_progress,
        average_physical_progress,
    ) = row

    completed_query = _query_with_work_ids(
        db.query(Project),
        work_ids,
    )

    completed_projects = (
        completed_query
        .filter(
            func.lower(Project.status)
            == "completed"
        )
        .count()
    )

    active_projects = (
        total_projects - completed_projects
    )

    expected_completion_query = (
        _query_with_work_ids(
            db.query(Project),
            work_ids,
        )
    )

    expected_completion_count = (
        expected_completion_query
        .filter(
            Project.expected_completion.isnot(None)
        )
        .count()
    )

    if expected_completion_count > 0:

        delayed_projects = (
            expected_completion_query
            .filter(
                func.lower(Project.status)
                != "completed",
                Project.expected_completion.isnot(None),
                Project.expected_completion
                < func.current_date(),
            )
            .count()
        )

        delayed_available = True
        delayed_reason = None

    else:

        delayed_projects = 0
        delayed_available = False
        delayed_reason = (
            "Expected completion data unavailable"
        )

    return {
        "total_projects": total_projects,
        "total_sanctioned_amount": (
            total_sanctioned_amount
        ),
        "total_expenditure": (
            total_expenditure
        ),
        "average_financial_progress": (
            average_financial_progress
        ),
        "average_physical_progress": (
            average_physical_progress
        ),
        "active_projects": active_projects,
        "completed_projects": completed_projects,
        "delayed_projects": delayed_projects,
        "delayed_projects_available": (
            delayed_available
        ),
        "delayed_projects_reason": (
            delayed_reason
        ),
    }


def compute_risk_level_counts(
    db: Session,
    work_ids: Optional[Sequence[str]] = None,
) -> dict[str, int]:

    query = _query_with_work_ids(
        db.query(
            Project.risk_level,
            func.count(Project.project_id),
        ),
        work_ids,
    )

    rows = (
        query
        .group_by(Project.risk_level)
        .all()
    )

    return {
        level: count
        for level, count in rows
        if level is not None
    }


def compute_by_state(
    db: Session,
    work_ids: Optional[Sequence[str]] = None,
) -> list[ByStateStat]:

    state_label = func.coalesce(
        Project.state,
        "Not specified",
    )

    query = _query_with_work_ids(
        db.query(
            state_label.label("state"),
            func.coalesce(
                func.sum(
                    Project.sanctioned_amount
                ),
                0,
            ),
            func.coalesce(
                func.sum(Project.expenditure),
                0,
            ),
        ),
        work_ids,
    )

    rows = (
        query
        .group_by(state_label)
        .order_by(
            desc(
                func.coalesce(
                    func.sum(Project.expenditure),
                    0,
                )
            )
        )
        .all()
    )

    return [
        ByStateStat(
            state=state,
            total_sanctioned_amount=sanctioned,
            total_expenditure=expenditure,
        )
        for state, sanctioned, expenditure in rows
    ]


def compute_by_work_type(
    db: Session,
    work_ids: Optional[Sequence[str]] = None,
) -> list[ByWorkTypeStat]:

    work_type_label = func.coalesce(
        func.nullif(
            func.trim(Project.work_type),
            "",
        ),
        "Not specified",
    )

    query = _query_with_work_ids(
        db.query(
            work_type_label.label("work_type"),
            func.count(Project.project_id),
        ),
        work_ids,
    )

    rows = (
        query
        .group_by(work_type_label)
        .order_by(
            desc(
                func.count(Project.project_id)
            )
        )
        .all()
    )

    return [
        ByWorkTypeStat(
            work_type=work_type,
            count=count,
        )
        for work_type, count in rows
    ]


def compute_risk_by_state(
    db: Session,
    work_ids: Optional[Sequence[str]] = None,
) -> list[StateRiskStat]:

    state_label = func.coalesce(
        Project.state,
        "Not specified",
    )

    query = _query_with_work_ids(
        db.query(
            state_label.label("state"),
            Project.risk_level,
            func.count(Project.project_id),
        ),
        work_ids,
    )

    rows = (
        query
        .group_by(
            state_label,
            Project.risk_level,
        )
        .all()
    )

    grouped = {}

    for state, level, count in rows:

        values = grouped.setdefault(
            state,
            {
                "low": 0,
                "medium": 0,
                "high": 0,
                "critical": 0,
            },
        )

        key = (level or "").lower()

        if key in values:
            values[key] = count

    return [
        StateRiskStat(
            state=state,
            **values,
        )
        for state, values in sorted(
            grouped.items()
        )
    ]


def compute_status_distribution(
    db: Session,
    work_ids: Optional[Sequence[str]] = None,
) -> list[StatusCount]:

    status_label = func.coalesce(
        func.nullif(
            func.trim(Project.status),
            "",
        ),
        "Not specified",
    )

    query = _query_with_work_ids(
        db.query(
            status_label.label("status"),
            func.count(Project.project_id),
        ),
        work_ids,
    )

    rows = (
        query
        .group_by(status_label)
        .order_by(
            desc(
                func.count(Project.project_id)
            )
        )
        .all()
    )

    return [
        StatusCount(
            status=status,
            count=count,
        )
        for status, count in rows
    ]


def compute_risk_score_summary(
    db: Session,
    work_ids: Optional[Sequence[str]] = None,
) -> dict:

    query = _query_with_work_ids(
        db.query(
            func.avg(Project.risk_score),
            func.min(Project.risk_score),
            func.max(Project.risk_score),
            func.count(Project.risk_score),
        ),
        work_ids,
    )

    (
        average,
        minimum,
        maximum,
        scored_count,
    ) = query.one()

    return {
        "average": average,
        "minimum": minimum,
        "maximum": maximum,
        "scored_project_count": scored_count,
    }


def compute_estimated_cost_summary(
    db: Session,
    work_ids: Optional[Sequence[str]] = None,
) -> dict:

    query = _query_with_work_ids(
        db.query(
            func.sum(Project.estimated_cost),
            func.avg(Project.estimated_cost),
            func.min(Project.estimated_cost),
            func.max(Project.estimated_cost),
            func.count(Project.estimated_cost),
        ),
        work_ids,
    )

    (
        total,
        average,
        minimum,
        maximum,
        count_with_data,
    ) = query.one()

    return {
        "total": total,
        "average": average,
        "minimum": minimum,
        "maximum": maximum,
        "project_count_with_data": count_with_data,
    }


def compute_progress_summary(
    db: Session,
    column,
    work_ids: Optional[Sequence[str]] = None,
) -> dict:

    query = _query_with_work_ids(
        db.query(
            func.avg(column),
            func.min(column),
            func.max(column),
            func.count(column),
        ),
        work_ids,
    )

    (
        average,
        minimum,
        maximum,
        count_with_data,
    ) = query.one()

    return {
        "average": average,
        "minimum": minimum,
        "maximum": maximum,
        "project_count_with_data": count_with_data,
    }
