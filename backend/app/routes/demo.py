"""
Public Demo API for MPLADS AI Shield.

Demo endpoints intentionally require no authentication.

- /public/*  -> anonymous-safe data, no risk intelligence
- /demo/*    -> full demonstration data + Risk Fusion intelligence
- /projects/* -> authenticated official API

The Demo dashboard and project browser use the same canonical project
universe and current Risk Fusion output as the authenticated API.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from typing import Any, List

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db

from app.routes.alerts import (
    SEVERITY_PRIORITY,
    _generate_alerts_for_row,
    _load_risk_fusion,
)

from app.aggregations import (
    load_canonical_projects,
    load_risk_fusion,
    compute_core_totals_from_canonical,
    compute_by_state_from_canonical,
    compute_by_work_type_from_canonical,
    compute_risk_level_counts_from_risk_fusion,
    compute_risk_by_state_from_risk_fusion,
    compute_status_distribution_from_canonical,
    compute_recent_projects_from_canonical
)

from app.routes.dashboard import _get_priority_projects
from app.routes.analytics import get_analytics
from app.routes.projects import (
    _apply_risk_to_project,
    _canonical_row_to_project,
    _clean_string,
    _load_project_datasets,
    _risk_map,
    _apply_canonical_filters,
    DEFAULT_LIMIT,
    MAX_LIMIT,
)

from app.schemas import (
    DashboardStats,
    ProjectOut,
    ProjectPage,
    RiskFusionOut,
    RoleDashboardResponse,
    AlertOut,
)


router = APIRouter(
    prefix="/demo",
    tags=["demo"],
)


# =====================================================================
# Helpers
# =====================================================================

def _load_demo_datasets():
    """
    Load the exact same canonical + Risk Fusion datasets used
    by the authenticated project endpoints.
    """
    return _load_project_datasets()


def _validate_demo_universe(
    canonical_df: pd.DataFrame,
    risk_df: pd.DataFrame,
) -> None:
    """
    Ensure the Demo dashboard/project browser uses one
    consistent project universe.
    """

    canonical_ids = set(
        canonical_df["work_id"]
        .astype(str)
        .str.strip()
    )

    risk_ids = set(
        risk_df["work_id"]
        .astype(str)
        .str.strip()
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


def _load_dashboard_datasets():
    """
    Load the same production dashboard datasets used by the
    authenticated Ministry dashboard.
    """

    try:
        canonical_df = load_canonical_projects()
        risk_df = load_risk_fusion()

    except (
        FileNotFoundError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )

    _validate_demo_universe(
        canonical_df,
        risk_df,
    )

    return canonical_df, risk_df


def _risk_result_from_row(
    project_id: str,
    row: pd.Series,
) -> RiskFusionOut:
    """
    Convert one Risk Fusion dataframe row into the API schema.
    """

    def _float(value: Any) -> float:
        numeric = pd.to_numeric(
            value,
            errors="coerce",
        )

        if pd.isna(numeric):
            return 0.0

        return float(numeric)

    def _int(value: Any) -> int:
        numeric = pd.to_numeric(
            value,
            errors="coerce",
        )

        if pd.isna(numeric):
            return 0

        return int(numeric)

    def _bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value

        if value is None or pd.isna(value):
            return False

        return str(value).strip().lower() in {
            "true",
            "1",
            "yes",
        }

    def _string_list(value: Any) -> list[str]:
        if value is None or pd.isna(value):
            return []

        if isinstance(value, list):
            return [
                str(item)
                for item in value
            ]

        text = str(value).strip()

        if not text:
            return []

        if (
            text.startswith("[")
            and text.endswith("]")
        ):
            try:
                parsed = ast.literal_eval(text)

                if isinstance(parsed, list):
                    return [
                        str(item)
                        for item in parsed
                    ]

            except Exception:
                pass

        return [text]

    def _dict_value(
        value: Any,
    ) -> dict[str, Any]:

        if value is None:
            return {}

        if isinstance(value, dict):
            return value

        if pd.isna(value):
            return {}

        text = str(value).strip()

        if not text:
            return {}

        try:
            parsed = ast.literal_eval(text)

            if isinstance(parsed, dict):
                return parsed

        except Exception:
            pass

        return {
            "raw": text
        }

    return RiskFusionOut(
        work_id=project_id,

        risk_score=_float(
            row["risk_score"]
        ),

        risk_level=str(
            row["risk_level"]
        ).upper().strip(),

        evidence_status=str(
            row["evidence_status"]
        ).upper().strip(),

        compliance_contribution=_float(
            row["compliance_contribution"]
        ),

        financial_anomaly_contribution=_float(
            row["financial_anomaly_contribution"]
        ),

        timeline_anomaly_contribution=_float(
            row["timeline_anomaly_contribution"]
        ),

        duplicate_contribution=_float(
            row["duplicate_contribution"]
        ),

        data_quality_contribution=_float(
            row["data_quality_contribution"]
        ),

        payment_contribution=_float(
            row["payment_contribution"]
        ),

        isolation_forest_contribution=_float(
            row["isolation_forest_contribution"]
        ),

        total_evidence_signals=_int(
            row["total_evidence_signals"]
        ),

        high_severity_signal_count=_int(
            row["high_severity_signal_count"]
        ),

        medium_severity_signal_count=_int(
            row["medium_severity_signal_count"]
        ),

        low_severity_signal_count=_int(
            row["low_severity_signal_count"]
        ),

        has_compliance_signal=_bool(
            row["has_compliance_signal"]
        ),

        has_financial_anomaly=_bool(
            row["has_financial_anomaly"]
        ),

        has_timeline_anomaly=_bool(
            row["has_timeline_anomaly"]
        ),

        has_duplicate_signal=_bool(
            row["has_duplicate_signal"]
        ),

        has_data_quality_signal=_bool(
            row["has_data_quality_signal"]
        ),

        has_payment_signal=_bool(
            row["has_payment_signal"]
        ),

        has_isolation_forest_signal=_bool(
            row["has_isolation_forest_signal"]
        ),

        top_reason_1=_clean_string(
            row.get("top_reason_1")
        ),

        top_reason_2=_clean_string(
            row.get("top_reason_2")
        ),

        top_reason_3=_clean_string(
            row.get("top_reason_3")
        ),

        risk_reasons=_string_list(
            row.get("risk_reasons")
        ),

        source_signal_summary=_dict_value(
            row.get("source_signal_summary")
        ),
    )


# =====================================================================
# DEMO DASHBOARD
# =====================================================================

@router.get(
    "/dashboard/stats",
    response_model=DashboardStats,
)
def get_demo_dashboard_stats():
    """
    Return the same national dashboard statistics available to
    authenticated Ministry/Admin users.

    No authentication is required because this is the intentional
    MPLADS AI Shield demonstration surface.
    """

    canonical_df, risk_df = _load_dashboard_datasets()

    totals = compute_core_totals_from_canonical(
        canonical_df
    )

    # DashboardStats requires delayed_projects to be an integer.
    # The canonical dataset may not have enough information to
    # calculate delayed projects, in which case the aggregation
    # returns None. Use 0 rather than failing schema validation.
    totals["delayed_projects"] = int(
        totals.get("delayed_projects") or 0
    )

    by_state = compute_by_state_from_canonical(
        canonical_df
    )

    by_work_type = compute_by_work_type_from_canonical(
        canonical_df
    )

    risk_level_counts = (
        compute_risk_level_counts_from_risk_fusion(
            risk_df
        )
    )

    return DashboardStats(
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


@router.get(
    "/dashboard/role-overview",
    response_model=RoleDashboardResponse,
)
def get_demo_role_dashboard(
    db: Session = Depends(get_db),
):
    """
    Return the complete national Ministry dashboard for Demo mode.
    """

    canonical_df, risk_df = _load_dashboard_datasets()

    totals = compute_core_totals_from_canonical(
        canonical_df
    )

    # DashboardStats requires delayed_projects to be an integer.
    # The canonical dataset may not have enough information to
    # calculate delayed projects, in which case the aggregation
    # returns None. Use 0 rather than failing schema validation.
    totals["delayed_projects"] = int(
        totals.get("delayed_projects") or 0
    )

    risk_level_counts = (
        compute_risk_level_counts_from_risk_fusion(
            risk_df
        )
    )

    by_state = compute_by_state_from_canonical(
        canonical_df
    )

    by_work_type = compute_by_work_type_from_canonical(
        canonical_df
    )

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

    priority_projects = _get_priority_projects(
        db=db,
        risk_df=risk_df,
        limit=12,
    )

    by_state_risk = (
        compute_risk_by_state_from_risk_fusion(
            canonical_df=canonical_df,
            risk_df=risk_df,
        )
    )

    return RoleDashboardResponse(
        role="Ministry / Admin",
        scope_available=True,
        scope_label="National",
        stats=stats,
        by_state_risk=by_state_risk,
        priority_projects=priority_projects,
    )



# =====================================================================
# DEMO ALERTS
# =====================================================================

@router.get(
    "/alerts",
    response_model=List[AlertOut],
)
def list_demo_alerts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    """
    Return the same AI Shield advisory alerts as the authenticated
    /alerts endpoint, but without requiring authentication.

    Demo mode uses the exact same production Risk Fusion output and
    alert-generation rules as the official authenticated API.
    """

    generated_at = datetime.now(timezone.utc)

    risk_df = _load_risk_fusion()

    raw_alerts: List[dict] = []

    for _, row in risk_df.iterrows():
        raw_alerts.extend(
            _generate_alerts_for_row(
                row,
                generated_at,
            )
        )

    raw_alerts.sort(
        key=lambda a: (
            SEVERITY_PRIORITY.get(a["severity"], 99),
            -a["sort_score"],
            a["project_id"],
            a["alert_type"],
        )
    )

    page = raw_alerts[skip: skip + limit]

    return [
        AlertOut(
            alert_id=a["alert_id"],
            project_id=a["project_id"],
            alert_type=a["alert_type"],
            severity=a["severity"],
            message=a["message"],
            created_at=generated_at,
        )
        for a in page
    ]
# =====================================================================
# DEMO ANALYTICS
# =====================================================================

@router.get(
    "/analytics",
)
def get_demo_analytics(
    db: Session = Depends(get_db),
):
    """
    Return the same national Analytics data as the authenticated
    /analytics endpoint, without requiring authentication.

    Demo mode intentionally uses the exact same production
    canonical project universe and Risk Fusion intelligence.
    """
    return get_analytics(db=db)

# =====================================================================
# DEMO PROJECT LIST
# =====================================================================

@router.get(
    "/projects",
    response_model=list[ProjectOut],
)
def list_demo_projects(
    skip: int = Query(
        0,
        ge=0,
        description="Number of projects to skip.",
    ),
    limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=(
            f"Maximum projects returned "
            f"in one page (1-{MAX_LIMIT})."
        ),
    ),
):
    """
    Return a page from the CURRENT 43,863-project canonical universe.

    Risk score and risk level are overlaid from current Risk Fusion.
    """

    canonical_df, risk_df = _load_demo_datasets()

    risk_lookup = _risk_map(
        risk_df
    )

    canonical_df = (
        canonical_df
        .sort_values("work_id")
    )

    page_df = (
        canonical_df
        .iloc[skip: skip + limit]
    )

    results = []

    for _, row in page_df.iterrows():

        project = _canonical_row_to_project(
            row
        )

        project = _apply_risk_to_project(
            project,
            risk_lookup.get(
                project.project_id
            ),
        )

        results.append(project)

    return results


# =====================================================================
# DEMO PROJECT QUERY
# =====================================================================

@router.get(
    "/projects/query",
    response_model=ProjectPage,
)
def query_demo_projects(
    skip: int = Query(
        0,
        ge=0,
        description="Number of projects to skip.",
    ),
    limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=(
            f"Maximum projects returned "
            f"in one page (1-{MAX_LIMIT})."
        ),
    ),
    state: str | None = Query(
        None,
        description="Filter by state.",
    ),
    category: str | None = Query(
        None,
        description="Filter by work category.",
    ),
    status_value: str | None = Query(
        None,
        alias="status",
        description="Filter by project status.",
    ),
    search: str | None = Query(
        None,
        max_length=120,
        description=(
            "Search project ID, state, district, "
            "constituency, work category, MP, or description."
        ),
    ),
):
    """
    Return a filtered page from the CURRENT 43,863-project
    canonical universe.
    """

    canonical_df, risk_df = _load_demo_datasets()

    risk_lookup = _risk_map(
        risk_df
    )

    filtered_df = _apply_canonical_filters(
        canonical_df,
        state,
        category,
        status_value,
        search,
    )

    filtered_df = (
        filtered_df
        .sort_values("work_id")
    )

    total = int(
        len(filtered_df)
    )

    page_df = (
        filtered_df
        .iloc[skip: skip + limit]
    )

    items = []

    for _, row in page_df.iterrows():

        project = _canonical_row_to_project(
            row
        )

        project = _apply_risk_to_project(
            project,
            risk_lookup.get(
                project.project_id
            ),
        )

        items.append(project)

    return ProjectPage(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


# =====================================================================
# DEMO PROJECT RISK
#
# IMPORTANT:
# The /risk route MUST come BEFORE the generic {project_id:path} route.
# =====================================================================

@router.get(
    "/projects/{project_id:path}/risk",
    response_model=RiskFusionOut,
)
def get_demo_project_risk(
    project_id: str,
):
    """
    Return the complete current Risk Fusion result.

    No authentication is required because this is the intentional
    MPLADS AI Shield demonstration surface.
    """

    _, risk_df = _load_demo_datasets()

    normalized_id = project_id.strip()

    matching = risk_df[
        risk_df["work_id"]
        .astype(str)
        .str.strip()
        == normalized_id
    ]

    if matching.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Demo Risk Fusion result for "
                f"project '{project_id}' is not available."
            ),
        )

    row = matching.iloc[0]

    return _risk_result_from_row(
        normalized_id,
        row,
    )


# =====================================================================
# DEMO SINGLE PROJECT
# =====================================================================

@router.get(
    "/projects/{project_id:path}",
    response_model=ProjectOut,
)
def get_demo_project(
    project_id: str,
):
    """
    Return a full project for the public demonstration mode.

    No authentication is required.

    Risk score and risk level are included because Demo is intentionally
    allowed to show the complete monitoring experience.
    """

    canonical_df, risk_df = _load_demo_datasets()

    normalized_id = project_id.strip()

    matching = canonical_df[
        canonical_df["work_id"]
        .astype(str)
        .str.strip()
        == normalized_id
    ]

    if matching.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Demo project '{project_id}' not found"
            ),
        )

    row = matching.iloc[0]

    project = _canonical_row_to_project(
        row
    )

    risk_lookup = _risk_map(
        risk_df
    )

    project = _apply_risk_to_project(
        project,
        risk_lookup.get(
            normalized_id
        ),
    )

    return project