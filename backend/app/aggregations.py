"""
Shared aggregation helpers.

There are two independent data surfaces in this module:

1. Canonical ML dataset (file-based):
       data/processed/canonical_projects.csv
       data/processed/project_risk_scores.csv (current Phase 7 Risk
       Fusion output)

   These are the authoritative 43,863-project project universe and the
   current ML/Risk Fusion output used for *national* project
   statistics. Dashboard/Analytics should prefer these for national
   totals so they stay consistent with the current Risk Fusion
   universe. This data has no per-user authorization boundary -- it is
   not scoped to a caller's jurisdiction -- so it must only be used
   where national/unrestricted statistics are the intended contract.

2. Authenticated Project database (`app.models.Project`):

   This remains available for legacy/API compatibility and for any
   authenticated application data that needs per-request scoping (e.g.
   Phase 8 jurisdiction/RBAC-scoped dashboards). Every helper in the
   "Legacy SQL helpers" section below accepts an already-authorized
   `query` (a SQLAlchemy Query the caller has already restricted to
   what the current user may see) and/or a `work_ids` allowlist, and
   NEVER widens that query back out to the full table. If both `query`
   and `work_ids` are supplied they are combined (AND'ed) rather than
   one silently overriding the other -- see `_scoped_query`.

   All SQL aggregation here is done in SQL (COUNT/SUM/AVG/MIN/MAX/
   GROUP BY) -- none of it pulls the full `projects` table into Python
   to aggregate there.

   NULL handling, consistent throughout the SQL helpers:
     - SQL AVG/MIN/MAX/COUNT(column) already ignore NULL rows for that
       column -- exactly the behavior wanted here (a project with no
       estimated_cost shouldn't drag the average toward zero or count
       as a min/max candidate). No manual NULL-filtering is needed for
       those.
     - Grouped fields (state, work_type, status) fold NULL/blank/
       whitespace-only values into an explicit "Not specified" bucket
       rather than dropping those projects from the total, and
       whitespace/case variants of the same value are merged into a
       single bucket, so grouped counts still reconcile with
       total_projects.
     - risk_level is the one exception: a NULL/blank risk_level means
       "not yet scored," which is not one of LOW/MEDIUM/HIGH/CRITICAL,
       so those rows are excluded from risk-level grouping entirely
       rather than folded into a bucket.
     - delayed_projects counts a project as delayed when its status is
       NULL *or* not "completed" (case/whitespace-insensitive) and it
       has an overdue expected_completion. A NULL status must not
       cause a project to be silently excluded from this count --
       that was a real bug (SQL's `NULL != 'completed'` evaluates to
       NULL, not true) and the fix here is preserved.
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
) -> list[dict]:
    """
    Combine canonical state metadata with current Risk Fusion risk
    levels.

    Returns a plain list[dict] -- {"state", "low", "medium", "high",
    "critical"} per row -- rather than a schema class, since no
    per-state risk-breakdown schema currently exists in app/schemas.py
    and no route in this repository consumes this function yet. If a
    route is later added to expose this, it should validate/serialize
    through whatever response schema that route defines.
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
            {
                "state": str(state),
                "low": int(
                    (levels == "LOW").sum()
                ),
                "medium": int(
                    (levels == "MEDIUM").sum()
                ),
                "high": int(
                    (levels == "HIGH").sum()
                ),
                "critical": int(
                    (levels == "CRITICAL").sum()
                ),
            }
        )

    return result


# =====================================================================
# Legacy SQL helpers
#
# These are retained so existing Analytics/other routes do not break,
# and so RBAC/jurisdiction-scoped routes (Phase 8) can pass an
# already-authorized `query` through the same aggregation logic used
# elsewhere. New Dashboard code that wants *national* totals should
# use the canonical helpers above; code that needs to reflect a
# specific caller's authorization boundary (or a specific work_id
# subset) should use the helpers below.
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


def _scoped_query(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
):
    """
    Build the base Project query for a legacy/RBAC-aware aggregation
    helper.

    - `query`: an already-authorized SQLAlchemy query (Phase 8
      RBAC/jurisdiction scoping). When provided, aggregation is
      computed over exactly this query and this function never widens
      it back out to the full `projects` table.
    - `work_ids`: an optional further restriction to a specific set of
      project IDs.

    When both are supplied they are combined (AND'ed together) rather
    than one silently overriding the other, so a caller can further
    restrict an already-authorized query but can never use `work_ids`
    to widen back out past what `query` already authorized.
    """

    base = query if query is not None else db.query(Project)

    return _query_with_work_ids(base, work_ids)


# ---------------------------------------------------------------------
# Normalization helpers
#
# These normalize (fold NULL/blank/whitespace/case variants into a
# single value) the grouped SQL columns below. Not to be confused with
# the "canonical" ML dataset above -- these just canonicalize a raw DB
# value into one consistent display label.
# ---------------------------------------------------------------------

def _normalized_state_label(value):
    if value is None:
        return "Not specified"
    normalized = str(value).strip()
    return normalized if normalized else "Not specified"


def _normalized_work_type_label(value):
    if value is None:
        return "Not specified"
    normalized = str(value).strip()
    return normalized if normalized else "Not specified"


def _normalized_status_label(value):
    if value is None:
        return "Not specified"
    normalized = str(value).strip()
    if not normalized:
        return "Not specified"
    if normalized.lower() == "not specified":
        return "Not specified"
    return normalized.title()


def _normalized_risk_label(value):
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized.upper()


def compute_core_totals(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> dict:
    """
    Project counts, financial totals, and progress averages, scoped to
    an already-authorized `query` and/or a `work_ids` allowlist.

    completed/active are determined by a case- and whitespace-
    insensitive comparison against "completed".

    delayed_projects counts a project as delayed when its status is
    NULL *or* not "completed" (case/whitespace-insensitive) and it has
    an overdue expected_completion -- a NULL status must not silently
    exclude an otherwise-overdue project from this count (Phase 10
    fix). When no project in scope has any expected_completion value
    at all, delayed_projects is reported as unavailable rather than
    silently defaulted to 0.
    """

    base_query = _scoped_query(db, query, work_ids)

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
        .filter(func.lower(func.trim(Project.status)) == "completed")
        .scalar()
    )
    active_projects = total_projects - completed_projects

    expected_completion_count = (
        base_query.with_entities(func.count(Project.project_id))
        .filter(Project.expected_completion.isnot(None))
        .scalar()
    )

    if expected_completion_count > 0:

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

        delayed_available = True
        delayed_reason = None

    else:

        delayed_projects = 0
        delayed_available = False
        delayed_reason = "Expected completion data unavailable"

    return {
        "total_projects": total_projects,
        "total_sanctioned_amount": total_sanctioned_amount,
        "total_expenditure": total_expenditure,
        "average_financial_progress": average_financial_progress,
        "average_physical_progress": average_physical_progress,
        "active_projects": active_projects,
        "completed_projects": completed_projects,
        "delayed_projects": delayed_projects,
        "delayed_projects_available": delayed_available,
        "delayed_projects_reason": delayed_reason,
    }


def compute_risk_level_counts(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> dict[str, int]:
    """
    GROUP BY count of Project.risk_level, scoped to an already-
    authorized `query` and/or a `work_ids` allowlist. NULL/blank
    values are ignored, and whitespace/case differences are
    normalized before bucketing so equivalent risk levels don't
    fragment into separate keys.
    """

    base_query = _scoped_query(db, query, work_ids)

    normalized_risk_level = func.lower(func.trim(Project.risk_level))

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
        _normalized_risk_label(level): count
        for level, count in rows
        if _normalized_risk_label(level) is not None
    }


def compute_by_state(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> list[ByStateStat]:
    """
    Sanctioned/expenditure totals grouped by state, scoped to an
    already-authorized `query` and/or a `work_ids` allowlist.
    NULL/blank values are folded into "Not specified" and
    spacing/case variants are merged into a single bucket.
    """

    base_query = _scoped_query(db, query, work_ids)

    state_bucket = func.coalesce(func.nullif(func.trim(Project.state), ""), "Not specified")
    state_key = func.lower(state_bucket)

    rows = (
        base_query.with_entities(
            state_key.label("state_key"),
            func.max(state_bucket).label("state"),
            func.coalesce(func.sum(Project.sanctioned_amount), 0),
            func.coalesce(func.sum(Project.expenditure), 0),
        )
        .group_by(state_key)
        .order_by(desc(func.coalesce(func.sum(Project.expenditure), 0)))
        .all()
    )

    return [
        ByStateStat(
            state=_normalized_state_label(state),
            total_sanctioned_amount=sanctioned,
            total_expenditure=expenditure,
        )
        for _, state, sanctioned, expenditure in rows
    ]


def compute_by_work_type(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> list[ByWorkTypeStat]:
    """
    Project count grouped by work_type, scoped to an already-
    authorized `query` and/or a `work_ids` allowlist. NULL and
    blank/whitespace-only work_type are both folded into
    "Not specified", and equivalent values are merged regardless of
    case/spacing.
    """

    base_query = _scoped_query(db, query, work_ids)

    work_type_bucket = func.coalesce(func.nullif(func.trim(Project.work_type), ""), "Not specified")
    work_type_key = func.lower(work_type_bucket)

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
        ByWorkTypeStat(work_type=_normalized_work_type_label(work_type), count=count)
        for _, work_type, count in rows
    ]


def compute_status_distribution(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> list[StatusCount]:
    """
    Project count grouped by status, scoped to an already-authorized
    `query` and/or a `work_ids` allowlist. NULL/blank status is
    folded into "Not specified", and equivalent values are merged
    regardless of case or surrounding whitespace.
    """

    base_query = _scoped_query(db, query, work_ids)

    status_bucket = func.coalesce(func.nullif(func.trim(Project.status), ""), "Not specified")
    status_key = func.lower(status_bucket)

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
        StatusCount(status=_normalized_status_label(status), count=count)
        for _, status, count in rows
    ]


def compute_risk_by_state(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> list[dict]:
    """
    Combine state and risk_level into per-state LOW/MEDIUM/HIGH/
    CRITICAL counts from the authenticated Project database, scoped
    to an already-authorized `query` and/or a `work_ids` allowlist.

    Applies the same state normalization used in compute_by_state
    (NULL/blank -> "Not specified", case/whitespace variants merged)
    and the same risk_level normalization used in
    compute_risk_level_counts (NULL/blank risk_level excluded, since
    it means "not yet scored" rather than a real bucket).

    Returns a plain list[dict] -- {"state", "low", "medium", "high",
    "critical"} per row -- rather than a schema class, since no
    per-state risk-breakdown schema currently exists in app/schemas.py
    and no route in this repository consumes this function yet. If a
    route is later added to expose this, it should validate/serialize
    through whatever response schema that route defines. RBAC scoping
    is preserved regardless of return type: this function never
    queries outside of `query`/`work_ids` once either is supplied --
    see `_scoped_query`.
    """

    base_query = _scoped_query(db, query, work_ids)

    state_bucket = func.coalesce(func.nullif(func.trim(Project.state), ""), "Not specified")
    state_key = func.lower(state_bucket)
    risk_level_key = func.lower(func.trim(Project.risk_level))

    # Determine one canonical display label per normalized state key,
    # independent of risk_level. Grouping display-label selection and
    # risk_level counts in a single (state_key, risk_level_key) query
    # would let MAX(state_bucket) pick a different casing per risk
    # level subgroup, silently splitting one state into multiple
    # displayed rows -- so the display label is resolved separately,
    # the same way compute_by_state resolves it.
    display_labels = dict(
        base_query.with_entities(state_key, func.max(state_bucket))
        .group_by(state_key)
        .all()
    )

    rows = (
        base_query.with_entities(
            state_key.label("state_key"),
            risk_level_key.label("risk_level_key"),
            func.count(Project.project_id),
        )
        .filter(
            func.trim(Project.risk_level).isnot(None),
            func.trim(Project.risk_level) != "",
        )
        .group_by(state_key, risk_level_key)
        .all()
    )

    grouped: dict[str, dict] = {}

    for key, risk_key, count in rows:

        display_state = _normalized_state_label(
            display_labels.get(key, key)
        )

        values = grouped.setdefault(
            display_state,
            {
                "low": 0,
                "medium": 0,
                "high": 0,
                "critical": 0,
            },
        )

        if risk_key in values:
            values[risk_key] = count

    return [
        {"state": state, **values}
        for state, values in sorted(grouped.items())
    ]


def compute_risk_score_summary(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> dict:
    """
    Average/min/max of Project.risk_score, plus how many projects
    actually have a (non-NULL) score, scoped to an already-authorized
    `query` and/or a `work_ids` allowlist. COUNT(risk_score) -- as
    opposed to COUNT(*) -- already skips NULL rows in SQL, so this is
    exactly the "how many were actually scored" count, not the full
    table size.
    """

    base_query = _scoped_query(db, query, work_ids)

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


def compute_estimated_cost_summary(
    db: Session,
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> dict:
    """
    Sum/average/min/max of Project.estimated_cost, plus how many
    projects actually have a value for it, scoped to an already-
    authorized `query` and/or a `work_ids` allowlist. Real Phase 2
    rows have no source value for estimated_cost at all (see
    app/models.py / import_phase2.py) -- so on the real dataset,
    project_count_with_data will legitimately be 0 or close to it,
    and the other fields will be null. This is reported explicitly
    rather than silently defaulted to 0.
    """

    base_query = _scoped_query(db, query, work_ids)

    total, average, minimum, maximum, count_with_data = base_query.with_entities(
        func.sum(Project.estimated_cost),
        func.avg(Project.estimated_cost),
        func.min(Project.estimated_cost),
        func.max(Project.estimated_cost),
        func.count(Project.estimated_cost),
    ).one()

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
    query=None,
    work_ids: Optional[Sequence[str]] = None,
) -> dict:
    """
    Average/min/max for a progress column (financial_progress or
    physical_progress), plus how many projects have a value for it,
    scoped to an already-authorized `query` and/or a `work_ids`
    allowlist. Generic over `column` so the same query logic backs
    both fields instead of two near-identical copies.
    """

    base_query = _scoped_query(db, query, work_ids)

    average, minimum, maximum, count_with_data = base_query.with_entities(
        func.avg(column),
        func.min(column),
        func.max(column),
        func.count(column),
    ).one()

    return {
        "average": average,
        "minimum": minimum,
        "maximum": maximum,
        "project_count_with_data": count_with_data,
    }