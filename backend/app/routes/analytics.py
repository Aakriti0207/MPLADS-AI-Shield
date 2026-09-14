"""
Route for GET /analytics.

Current Analytics architecture:

    canonical_projects.csv
            +
    project_risk_scores.csv
            ↓
        /analytics

The canonical dataset is the authoritative project universe for
portfolio-level statistics.

The Phase 7 Risk Fusion output is the authoritative source for
AI risk scores and risk levels.

The database is not used as the source of truth for national
analytics because the database contains only a partial overlap
with the current 43,863-project canonical universe.
"""

from typing import Any

import pandas as pd

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy.orm import Session

from app.aggregations import (
    load_canonical_projects,
    load_risk_fusion,
    compute_core_totals_from_canonical,
    compute_by_state_from_canonical,
    compute_by_work_type_from_canonical,
    compute_risk_level_counts_from_risk_fusion,
)

from app.database import get_db
from app.auth import get_current_user

from app.schemas import (
    AnalyticsResponse,
    EstimatedCostSummary,
    ProgressSummary,
    RiskScoreSummary,
)


# =====================================================================
# Router
# =====================================================================

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(get_current_user)],
)


# =====================================================================
# Helpers
# =====================================================================

def _validate_universe(
    canonical_df: pd.DataFrame,
    risk_df: pd.DataFrame,
) -> None:
    """
    Make sure the canonical project universe and Risk Fusion universe
    are identical.

    Dashboard and Analytics must never silently operate on different
    project populations.
    """

    canonical_ids = set(
        canonical_df["work_id"]
    )

    risk_ids = set(
        risk_df["work_id"]
    )

    if canonical_ids != risk_ids:

        missing_risk = canonical_ids - risk_ids
        extra_risk = risk_ids - canonical_ids

        raise HTTPException(
            status_code=503,
            detail=(
                "Canonical and Risk Fusion project universes "
                "do not match. "
                f"Canonical={len(canonical_ids)}, "
                f"RiskFusion={len(risk_ids)}, "
                f"missing_risk={len(missing_risk)}, "
                f"extra_risk={len(extra_risk)}."
            ),
        )


def _numeric(
    df: pd.DataFrame,
    column: str,
) -> pd.Series:
    """
    Safely convert a canonical column to numeric.
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
# Risk score summary
# =====================================================================

def _risk_score_summary(
    risk_df: pd.DataFrame,
) -> dict[str, Any]:
    """
    Summary of CURRENT Risk Fusion scores.

    This replaces the legacy Project.risk_score aggregation.
    """

    scores = pd.to_numeric(
        risk_df["risk_score"],
        errors="coerce",
    ).dropna()

    if scores.empty:

        return {
            "average": None,
            "minimum": None,
            "maximum": None,
            "scored_project_count": 0,
        }

    return {
        "average": float(scores.mean()),
        "minimum": float(scores.min()),
        "maximum": float(scores.max()),
        "scored_project_count": int(
            scores.count()
        ),
    }


# =====================================================================
# Estimated cost summary
# =====================================================================

def _estimated_cost_summary(
    canonical_df: pd.DataFrame,
) -> dict[str, Any]:
    """
    Estimated-cost summary.

    The current canonical_projects.csv does NOT contain an
    estimated_cost column.

    Therefore we explicitly report the metric as unavailable instead
    of incorrectly using sanction_amount as estimated cost.
    """

    if "estimated_cost" not in canonical_df.columns:

        return {
            "total": None,
            "average": None,
            "minimum": None,
            "maximum": None,
            "project_count_with_data": 0,
        }

    values = pd.to_numeric(
        canonical_df["estimated_cost"],
        errors="coerce",
    ).dropna()

    if values.empty:

        return {
            "total": None,
            "average": None,
            "minimum": None,
            "maximum": None,
            "project_count_with_data": 0,
        }

    return {
        "total": float(values.sum()),
        "average": float(values.mean()),
        "minimum": float(values.min()),
        "maximum": float(values.max()),
        "project_count_with_data": int(
            values.count()
        ),
    }


# =====================================================================
# Financial progress summary
# =====================================================================

def _financial_progress_summary(
    canonical_df: pd.DataFrame,
) -> dict[str, Any]:
    """
    Calculate financial progress from canonical financial data.

    Formula:

        total_expenditure / sanction_amount * 100

    This is calculated per project and then summarized.
    """

    sanction = _numeric(
        canonical_df,
        "sanction_amount",
    )

    expenditure = _numeric(
        canonical_df,
        "total_expenditure",
    )

    valid = sanction > 0

    if not valid.any():

        return {
            "average": None,
            "minimum": None,
            "maximum": None,
            "project_count_with_data": 0,
        }

    progress = (
        expenditure[valid]
        / sanction[valid]
        * 100
    )

    return {
        "average": float(progress.mean()),
        "minimum": float(progress.min()),
        "maximum": float(progress.max()),
        "project_count_with_data": int(
            progress.count()
        ),
    }


# =====================================================================
# Physical progress summary
# =====================================================================

def _physical_progress_summary(
    canonical_df: pd.DataFrame,
) -> dict[str, Any]:
    """
    Physical progress is not available in the current canonical
    dataset.
    """

    if "physical_progress" not in canonical_df.columns:

        return {
            "average": None,
            "minimum": None,
            "maximum": None,
            "project_count_with_data": 0,
        }

    values = pd.to_numeric(
        canonical_df["physical_progress"],
        errors="coerce",
    ).dropna()

    if values.empty:

        return {
            "average": None,
            "minimum": None,
            "maximum": None,
            "project_count_with_data": 0,
        }

    return {
        "average": float(values.mean()),
        "minimum": float(values.min()),
        "maximum": float(values.max()),
        "project_count_with_data": int(
            values.count()
        ),
    }


# =====================================================================
# Status distribution
# =====================================================================

def _status_distribution(
    canonical_df: pd.DataFrame,
) -> list[dict[str, Any]]:
    """
    Count projects by current canonical status.
    """

    if "status" not in canonical_df.columns:
        return []

    status = (
        canonical_df["status"]
        .fillna("Not specified")
        .astype(str)
        .str.strip()
    )

    status = status.replace(
        "",
        "Not specified",
    )

    counts = (
        status
        .value_counts()
        .sort_values(
            ascending=False
        )
    )

    return [
        {
            "status": str(name),
            "count": int(count),
        }
        for name, count in counts.items()
    ]


# =====================================================================
# GET /analytics
# =====================================================================

@router.get(
    "",
    response_model=AnalyticsResponse,
)
def get_analytics(
    db: Session = Depends(get_db),
):
    """
    Return the complete national Analytics contract.

    Source of truth:

        Project universe:
            canonical_projects.csv

        AI risk:
            project_risk_scores.csv

    The DB session remains in the signature for compatibility with
    the protected application route, but national Analytics does not
    aggregate the incomplete Project table.
    """

    # ---------------------------------------------------------------
    # Load canonical project universe.
    # ---------------------------------------------------------------

    try:

        canonical_df = (
            load_canonical_projects()
        )

        risk_df = (
            load_risk_fusion()
        )

    except (
        FileNotFoundError,
        ValueError,
    ) as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )

    # ---------------------------------------------------------------
    # Make sure both datasets represent exactly the same projects.
    # ---------------------------------------------------------------

    _validate_universe(
        canonical_df,
        risk_df,
    )

    # ---------------------------------------------------------------
    # Core portfolio totals
    # ---------------------------------------------------------------

    totals = (
        compute_core_totals_from_canonical(
            canonical_df
        )
    )

    # ---------------------------------------------------------------
    # Current Risk Fusion distribution
    # ---------------------------------------------------------------

    risk_level_counts = (
        compute_risk_level_counts_from_risk_fusion(
            risk_df
        )
    )

    # ---------------------------------------------------------------
    # State aggregation
    # ---------------------------------------------------------------

    by_state = (
        compute_by_state_from_canonical(
            canonical_df
        )
    )

    # ---------------------------------------------------------------
    # Work category aggregation
    # ---------------------------------------------------------------

    by_work_type = (
        compute_by_work_type_from_canonical(
            canonical_df
        )
    )

    # ---------------------------------------------------------------
    # CURRENT Risk Fusion score summary
    # ---------------------------------------------------------------

    risk_score_summary = RiskScoreSummary(
        **_risk_score_summary(
            risk_df
        )
    )

    # ---------------------------------------------------------------
    # Estimated cost
    #
    # Current canonical data does not contain estimated_cost.
    # ---------------------------------------------------------------

    estimated_cost_summary = (
        EstimatedCostSummary(
            **_estimated_cost_summary(
                canonical_df
            )
        )
    )

    # ---------------------------------------------------------------
    # Financial progress
    # ---------------------------------------------------------------

    financial_progress_summary = (
        ProgressSummary(
            **_financial_progress_summary(
                canonical_df
            )
        )
    )

    # ---------------------------------------------------------------
    # Physical progress
    # ---------------------------------------------------------------

    physical_progress_summary = (
        ProgressSummary(
            **_physical_progress_summary(
                canonical_df
            )
        )
    )

    # ---------------------------------------------------------------
    # Status distribution
    # ---------------------------------------------------------------

    status_distribution = (
        _status_distribution(
            canonical_df
        )
    )

    # ---------------------------------------------------------------
    # Final response
    # ---------------------------------------------------------------

    return AnalyticsResponse(
        **totals,

        risk_level_counts=(
            risk_level_counts
        ),

        by_state=by_state,

        by_work_type=by_work_type,

        risk_score_summary=(
            risk_score_summary
        ),

        estimated_cost_summary=(
            estimated_cost_summary
        ),

        financial_progress_summary=(
            financial_progress_summary
        ),

        physical_progress_summary=(
            physical_progress_summary
        ),

        status_distribution=(
            status_distribution
        ),
    )