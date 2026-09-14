"""
Routes for the `projects` resource.

Keeps route logic thin: sessions come from the `get_db` dependency,
queries go straight against the SQLAlchemy model, and serialization
is handled entirely by the Pydantic response_model. No business logic
lives here beyond a 404 check.

Phase 2 update:
    `GET /projects` was previously returning all 56,323 rows in a single
    response. Pagination is now applied directly at the database level.

Pagination:
    - `skip` controls the number of rows to skip.
    - `limit` controls the maximum number of rows returned.
    - Results are ordered by `project_id` for stable paging.

The frontend currently requests up to 300 projects, so MAX_LIMIT is set
to 300. This still prevents the endpoint from returning the entire
56,323-row dataset in a single request.

No existing filters existed on this route to preserve -- it was a plain
`db.query(Project).all()` -- so the filters on `/projects/query` remain
additive.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import Project
from app.schemas import ProjectOut, ProjectPage, RiskFusionOut
from app.services.ml_service import get_risk_fusion_result


router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------
# Pagination configuration
# ---------------------------------------------------------------

DEFAULT_LIMIT = 50

# The frontend currently requests:
#     /projects?skip=0&limit=300
#
# Therefore the API must allow 300 rows.
# This is still safely bounded and avoids returning all 56,323 rows.
MAX_LIMIT = 300


# ---------------------------------------------------------------
# Shared project filters
# ---------------------------------------------------------------

def _project_filters(
    query,
    state: str | None,
    category: str | None,
    status_value: str | None,
    search: str | None,
):
    """
    Apply optional project filters to an existing SQLAlchemy query.
    """

    if state:
        query = query.filter(Project.state == state)

    if category:
        query = query.filter(Project.work_type == category)

    if status_value:
        query = query.filter(Project.status == status_value)

    if search:
        pattern = f"%{search}%"

        query = query.filter(
            or_(
                Project.project_id.ilike(pattern),
                Project.state.ilike(pattern),
                Project.constituency.ilike(pattern),
                Project.work_type.ilike(pattern),
                Project.mp_name.ilike(pattern),
            )
        )

    return query


# ---------------------------------------------------------------
# GET /projects
# ---------------------------------------------------------------

@router.get(
    "",
    response_model=List[ProjectOut],
)
def list_projects(
    skip: int = Query(
        0,
        ge=0,
        description="Number of projects to skip (for paging).",
    ),
    limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=f"Max projects to return in one page (1-{MAX_LIMIT}).",
    ),
    db: Session = Depends(get_db),
):
    """
    Return a page of projects.

    Pagination is performed at the database level using OFFSET/LIMIT.

    Results are ordered by project_id to provide deterministic paging.
    """

    return (
        db.query(Project)
        .order_by(Project.project_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------
# GET /projects/query
# ---------------------------------------------------------------

@router.get(
    "/query",
    response_model=ProjectPage,
)
def query_projects(
    skip: int = Query(
        0,
        ge=0,
        description="Number of projects to skip.",
    ),
    limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=f"Max projects to return in one page (1-{MAX_LIMIT}).",
    ),
    state: str | None = Query(
        None,
        description="Filter by state.",
    ),
    category: str | None = Query(
        None,
        description="Filter by work type/category.",
    ),
    status_value: str | None = Query(
        None,
        alias="status",
        description="Filter by project status.",
    ),
    search: str | None = Query(
        None,
        max_length=120,
        description="Search project ID, state, constituency, work type, or MP name.",
    ),
    db: Session = Depends(get_db),
):
    """
    Return a filtered authenticated project page.

    Unlike GET /projects, this endpoint also returns the total number
    of projects matching the filters.
    """

    query = _project_filters(
        db.query(Project),
        state,
        category,
        status_value,
        search,
    )

    total = query.count()

    items = (
        query
        .order_by(Project.project_id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    return ProjectPage(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


# ---------------------------------------------------------------
# GET /projects/{project_id}/risk
# ---------------------------------------------------------------

@router.get(
    "/{project_id:path}/risk",
    response_model=RiskFusionOut,
)
def get_project_risk(
    project_id: str,
    db: Session = Depends(get_db),
):
    """
    Return the current Phase 9 Risk Fusion result for an existing
    project.

    The legacy Phase 2 risk fields remain available through the normal
    project endpoint for compatibility.

    This endpoint explicitly uses the current Risk Fusion service and
    does not fall back to legacy Phase 2 risk values.
    """

    # First verify that the project exists.
    project = (
        db.query(Project.project_id)
        .filter(Project.project_id == project_id)
        .first()
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )

    # Fetch the current Risk Fusion result.
    result = get_risk_fusion_result(project_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Current Risk Fusion result for project "
                f"'{project_id}' is not available"
            ),
        )

    return result


# ---------------------------------------------------------------
# GET /projects/{project_id}
# ---------------------------------------------------------------

@router.get(
    "/{project_id:path}",
    response_model=ProjectOut,
)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
):
    """
    Return a single project by project_id.

    Returns 404 when the requested project does not exist.
    """

    project = (
        db.query(Project)
        .filter(Project.project_id == project_id)
        .first()
    )

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )

    return project