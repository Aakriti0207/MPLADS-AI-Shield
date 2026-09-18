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

RBAC
----
GET /dashboard/role-overview returns a genuinely different dashboard
per role, computed over a genuinely different set of records:

    Ministry / Admin      -> nationwide (unchanged from before)
    State Nodal Authority -> one assigned state, with district comparison
    District Authority    -> one assigned district, with a review queue
    MP                    -> one assigned constituency

The scope is derived from the authenticated user (app/rbac.py), so the
figures are aggregated from the scoped frame directly. A scoped role
never fetches the national aggregate and hides part of it -- which is
both the security property and the reason these dashboards are fast.
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
    ScopeInfo,
)

from app.rbac import (
    ROLE_MINISTRY,
    UserScope,
    get_scope,
    role_config,
    scope_frames,
)

from app.role_dashboards import (
    compute_attention_projects,
    compute_category_distribution,
    compute_district_performance,
    compute_kpis,
    compute_project_rows,
    compute_risk_level_counts,
    compute_status_distribution,
    data_notes,
    merge_scoped,
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
    scope: UserScope = Depends(get_scope),
):
    """
    Return Dashboard statistics for the caller's authorized scope.

    Project universe:
        canonical_projects.csv

    AI risk:
        project_risk_scores.csv

    Ministry/Admin receives the full 43,863-project universe, exactly as
    this endpoint always has. Every other role receives the same
    statistics computed over its own jurisdiction only, and an account
    with no jurisdiction assigned receives zeroes rather than national
    figures.

    Both frames are scoped to the same work_id set, so the project total
    and the Risk Fusion distribution below still describe one identical
    universe -- the universe-equality guard is unaffected.
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
    # RBAC: reduce BOTH frames to the caller's authorized universe
    # before any aggregate is computed.
    # ---------------------------------------------------------------

    canonical_df, risk_df = scope_frames(
        canonical_df,
        risk_df,
        scope,
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
    scope: UserScope = Depends(get_scope),
):
    """
    Return the dashboard authorized for the authenticated user's role.

    Ministry/Admin users receive the national dashboard, unchanged.
    State Nodal, District Authority and MP accounts receive a dashboard
    built from their own jurisdiction's records -- different figures,
    different tables, different priorities, one shared risk engine.

    All project statistics come from canonical_projects.csv.
    All AI risk values come from project_risk_scores.csv.
    """

    role = current_user.role or ""
    config = role_config(scope.role)

    # ---------------------------------------------------------------
    # Scoped roles (State Nodal / District Authority / MP) and
    # accounts with no jurisdiction assigned.
    #
    # Handled before the Ministry path below so the national branch
    # stays byte-for-byte what it already was.
    # ---------------------------------------------------------------

    if scope.role != ROLE_MINISTRY:
        return _scoped_role_dashboard(role, scope, config)

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
    totals["delayed_projects"] = int(totals.get("delayed_projects") or 0)
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
        # Additive RBAC payload. The seven fields above are the original
        # Ministry contract and are unchanged; everything below simply
        # tells the frontend which persona it is rendering.
        role_key=scope.role,
        role_label=scope.role_label,
        dashboard=role_config(scope.role)["dashboard"],
        permissions=sorted(scope.permissions),
        scope=ScopeInfo(**scope.as_metadata()),
        scope_indicator=scope.scope_indicator,
    )

# =====================================================================
# Scoped dashboards: State Nodal / District Authority / MP
# =====================================================================

def _scoped_role_dashboard(
    role: str,
    scope: UserScope,
    config: dict,
) -> RoleDashboardResponse:
    """
    Build the dashboard for a jurisdictional role.

    The shape of the response is the same for all three personas -- KPIs,
    distributions, an attention queue and a project table -- because they
    share one design system and one set of components. What differs is
    the records it is computed from, and which blocks the role's cockpit
    puts first (district comparison for State Nodal, the review queue for
    District Authority, project progress for an MP).

    An account with no assigned jurisdiction returns scope_available=False
    with an explanatory message. It does NOT fall through to national
    data.
    """

    base = dict(
        role=role,
        role_key=scope.role,
        role_label=scope.role_label,
        dashboard=config["dashboard"],
        permissions=sorted(scope.permissions),
        scope=ScopeInfo(**scope.as_metadata()),
        scope_indicator=scope.scope_indicator,
        scope_label=scope.scope_label,
        empty_state_message=scope.empty_state_message,
    )

    if scope.is_empty:
        return RoleDashboardResponse(
            scope_available=False,
            unavailable_reason=scope.unavailable_reason,
            **base,
        )

    # -----------------------------------------------------------------
    # Load, then immediately reduce to the authorized universe. Every
    # aggregate below is computed from the scoped frame -- nothing
    # national is ever computed and then withheld.
    # -----------------------------------------------------------------

    try:
        canonical_df = load_canonical_projects()
        risk_df = load_risk_fusion()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    canonical_df, risk_df = scope_frames(canonical_df, risk_df, scope)

    merged = merge_scoped(canonical_df, risk_df)

    kpis = compute_kpis(merged, scope)

    # District comparison is meaningful only for a scope that spans
    # more than one district, i.e. State Nodal. A District Authority
    # gets its review queue instead.
    district_performance = (
        compute_district_performance(merged)
        if scope.can("VIEW_DISTRICT_COMPARISON") and scope.scope_type == "state"
        else []
    )

    return RoleDashboardResponse(
        scope_available=True,
        kpis=kpis,
        status_distribution=compute_status_distribution(merged),
        by_work_category=compute_category_distribution(merged),
        risk_level_counts=compute_risk_level_counts(merged),
        district_performance=district_performance,
        attention_projects=compute_attention_projects(merged, limit=20),
        scoped_projects=compute_project_rows(merged, limit=50),
        data_notes=data_notes(merged, scope),
        **base,
    )