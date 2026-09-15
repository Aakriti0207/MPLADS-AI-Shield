"""
Dashboard routes.

Current architecture:

    canonical_projects.csv
            +
    project_risk_scores.csv
            ↓
        Dashboard

The canonical project dataset is the authoritative project universe
for national Dashboard statistics.

The Phase 7 Risk Fusion output is the authoritative source for AI risk.

The database is used only where the API contract requires existing
Project/User objects.
"""

from pathlib import Path
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
    compute_risk_by_state_from_risk_fusion,
    compute_status_distribution_from_canonical,
    compute_recent_projects_from_canonical,
)

from app.database import get_db
from app.auth import get_current_user
from app.models import Project, User

from app.schemas import (
    DashboardStats,
    RoleDashboardResponse,
    ProjectOut,
)


# =====================================================================
# Router
# =====================================================================

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)


# =====================================================================
# Priority project helper
# =====================================================================

def _get_priority_projects(
    db: Session,
    risk_df: pd.DataFrame,
    limit: int = 12,
) -> list[ProjectOut]:
    """
    Return the highest-risk projects according to CURRENT Risk Fusion.

    Risk score and risk level come from project_risk_scores.csv.

    ProjectOut metadata is supplied from the Project DB when a matching
    DB record exists.

    This does NOT modify or persist the database.
    """

    priority_df = risk_df[
        risk_df["risk_level"]
        .astype(str)
        .str.upper()
        .str.strip()
        .isin(
            [
                "MEDIUM",
                "HIGH",
                "CRITICAL",
            ]
        )
    ].copy()

    if priority_df.empty:
        return []

    priority_df["risk_score_numeric"] = pd.to_numeric(
        priority_df["risk_score"],
        errors="coerce",
    ).fillna(0)

    priority_df = (
        priority_df
        .sort_values(
            by=[
                "risk_score_numeric",
                "work_id",
            ],
            ascending=[
                False,
                True,
            ],
        )
        .head(limit)
    )

    project_ids = (
        priority_df["work_id"]
        .astype(str)
        .tolist()
    )

    # ---------------------------------------------------------------
    # Fetch matching DB projects.
    #
    # Some canonical projects may not have a corresponding Project
    # DB row. Those cannot be returned as ProjectOut because that
    # response schema represents the DB Project model.
    # ---------------------------------------------------------------

    projects = (
        db.query(Project)
        .filter(
            Project.project_id.in_(project_ids)
        )
        .all()
    )

    project_map = {
        str(project.project_id).strip(): project
        for project in projects
    }

    results: list[ProjectOut] = []

    for _, risk_row in priority_df.iterrows():

        project_id = (
            str(risk_row["work_id"])
            .strip()
        )

        project = project_map.get(
            project_id
        )

        if project is None:
            continue

        project_out = ProjectOut.model_validate(
            project
        )

        # -----------------------------------------------------------
        # Overlay CURRENT Risk Fusion values on the response.
        # -----------------------------------------------------------

        project_out = project_out.model_copy(
            update={
                "risk_score": risk_row[
                    "risk_score"
                ],
                "risk_level": (
                    str(
                        risk_row["risk_level"]
                    )
                    .upper()
                    .strip()
                ),
            }
        )

        results.append(project_out)

    return results


# =====================================================================
# GET /dashboard/stats
# =====================================================================

@router.get(
    "/stats",
    response_model=DashboardStats,
)
def get_dashboard_stats(
    db: Session = Depends(get_db),
):
    """
    Return national Dashboard statistics.

    Project universe:
        canonical_projects.csv

    AI risk:
        project_risk_scores.csv

    This ensures the project total and Risk Fusion risk distribution
    refer to the same 43,863-project universe.
    """

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
    # Safety check: canonical and Risk Fusion universes
    # ---------------------------------------------------------------

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

    # ---------------------------------------------------------------
    # Core project totals
    # ---------------------------------------------------------------

    totals = (
        compute_core_totals_from_canonical(
            canonical_df
        )
    )

    # ---------------------------------------------------------------
    # Financial aggregation by state
    # ---------------------------------------------------------------

    by_state = (
        compute_by_state_from_canonical(
            canonical_df
        )
    )

    # ---------------------------------------------------------------
    # Project count by work category
    # ---------------------------------------------------------------

    by_work_type = (
        compute_by_work_type_from_canonical(
            canonical_df
        )
    )

    # ---------------------------------------------------------------
    # CURRENT Risk Fusion distribution
    # ---------------------------------------------------------------

    risk_level_counts = (
        compute_risk_level_counts_from_risk_fusion(
            risk_df
        )
    )

    # ---------------------------------------------------------------
    # Phase 4: status distribution and recently active projects
    # ---------------------------------------------------------------

    status_distribution = (
        compute_status_distribution_from_canonical(
            canonical_df
        )
    )

    recent_projects = (
        compute_recent_projects_from_canonical(
            canonical_df,
            limit=8,
        )
    )

    # ---------------------------------------------------------------
    # Response
    # ---------------------------------------------------------------

    return DashboardStats(
        **totals,
        risk_level_counts=risk_level_counts,
        by_state=by_state,
        by_work_type=by_work_type,
        status_distribution=status_distribution,
        recent_projects=recent_projects,
    )


# =====================================================================
# GET /dashboard/role-overview
# =====================================================================

@router.get(
    "/role-overview",
    response_model=RoleDashboardResponse,
)
def get_role_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return dashboard data authorized by the authenticated user's role.

    Ministry/Admin users receive the national dashboard.

    All national project statistics come from canonical_projects.csv.

    All AI risk values come from project_risk_scores.csv.
    """

    role = current_user.role or ""

    # ---------------------------------------------------------------
    # Role authorization
    # ---------------------------------------------------------------

    is_ministry = (
        "admin" in role.lower()
        or "ministry" in role.lower()
    )

    if not is_ministry:

        return RoleDashboardResponse(
            role=role,
            scope_available=False,
            unavailable_reason=(
                "Scoped dashboard data is not available because the "
                "authenticated user has no state, district, constituency, "
                "or MP scope configured."
            ),
        )

    # ---------------------------------------------------------------
    # Load both current production datasets.
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
    # Verify that both production datasets describe the same universe.
    # ---------------------------------------------------------------

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

    # ---------------------------------------------------------------
    # Core national totals
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
    # State financial aggregation
    # ---------------------------------------------------------------

    by_state = (
        compute_by_state_from_canonical(
            canonical_df
        )
    )

    # ---------------------------------------------------------------
    # Work-category aggregation
    # ---------------------------------------------------------------

    by_work_type = (
        compute_by_work_type_from_canonical(
            canonical_df
        )
    )

    # ---------------------------------------------------------------
    # Dashboard stats
    # ---------------------------------------------------------------

    stats = DashboardStats(
        **totals,
        risk_level_counts=risk_level_counts,
        by_state=by_state,
        by_work_type=by_work_type,
        status_distribution=compute_status_distribution_from_canonical(
            canonical_df
        ),
        recent_projects=compute_recent_projects_from_canonical(
            canonical_df,
            limit=8,
        ),
    )

    # ---------------------------------------------------------------
    # Current Risk Fusion priority projects
    # ---------------------------------------------------------------

    priority_projects = (
        _get_priority_projects(
            db=db,
            risk_df=risk_df,
            limit=12,
        )
    )

    # ---------------------------------------------------------------
    # Current Risk Fusion risk by state
    # ---------------------------------------------------------------

    by_state_risk = (
        compute_risk_by_state_from_risk_fusion(
            canonical_df=canonical_df,
            risk_df=risk_df,
        )
    )

    # ---------------------------------------------------------------
    # Final response
    # ---------------------------------------------------------------

    return RoleDashboardResponse(
        role=role,
        scope_available=True,
        scope_label="National",
        stats=stats,
        by_state_risk=by_state_risk,
        priority_projects=priority_projects,
    )