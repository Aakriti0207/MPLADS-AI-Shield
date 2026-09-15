"""
Routes for the `projects` resource.

Keeps route logic thin: sessions come from the `get_db` dependency,
queries go straight against the SQLAlchemy model, and serialization
is handled entirely by the Pydantic response_model. No business logic
lives here beyond a 404 check.

Phase 2 update: `GET /projects` was returning all 56,323 rows in a
single response (fine at the DB layer, but enough to make Swagger/Chrome
hang while it tries to render that much JSON). Added `skip`/`limit`
query parameters, applied as `.offset()/.limit()` on the SQLAlchemy
query itself -- so Postgres only ever selects the requested page, not
"select everything, then slice in Python" (that would still pull all
56,323 rows into the app's memory on every call, just discarding most
of them afterward -- no better than before from the database's or the
network's perspective).

No existing filters existed on this route to preserve -- it was a plain
`db.query(Project).all()` -- so this is purely additive.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import authorize_project_access, get_current_user, user_project_scope_filter
from app.models import Project, User
from app.schemas import ProjectOut, ProjectRiskOut
from app.services.ml_service import get_project_risk

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    dependencies=[Depends(get_current_user)],
)

DEFAULT_LIMIT = 50
MAX_LIMIT = 100


@router.get("", response_model=List[ProjectOut])
def list_projects(
    skip: int = Query(0, ge=0, description="Number of projects to skip (for paging)."),
    limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=f"Max projects to return in one page (1-{MAX_LIMIT}).",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return a page of projects, ordered by `project_id` for stable paging.

    Pagination is applied at the database level (`.offset().limit()`),
    so a single request only ever selects up to `limit` rows from
    Postgres -- it never loads the full 56,323-row table into memory
    and slices it in Python.

    An explicit `.order_by(Project.project_id)` was added: without a
    deterministic order, Postgres doesn't guarantee row order across
    separate `OFFSET`/`LIMIT` queries, so consecutive pages could
    overlap or skip rows. This doesn't change which rows exist or any
    Phase 2 data -- only the order results are returned in.
    """
    query = user_project_scope_filter(current_user, db.query(Project))
    return query.order_by(Project.project_id).offset(skip).limit(limit).all()


@router.get("/query", response_model=List[ProjectOut])
def query_projects(
    state: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    constituency: Optional[str] = Query(None),
    category: Optional[str] = Query(None, description="Work type/category to match."),
    work_type: Optional[str] = Query(None),
    project_status: Optional[str] = Query(None, alias="status"),
    risk_level: Optional[str] = Query(None),
    skip: int = Query(0, ge=0, description="Number of projects to skip (for paging)."),
    limit: int = Query(
        DEFAULT_LIMIT,
        ge=1,
        le=MAX_LIMIT,
        description=f"Max projects to return in one page (1-{MAX_LIMIT}).",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a filtered, database-backed page of projects."""
    query = user_project_scope_filter(current_user, db.query(Project))
    filters = {
        Project.state: state,
        Project.district: district,
        Project.constituency: constituency,
        Project.status: project_status,
        Project.risk_level: risk_level,
    }
    for column, value in filters.items():
        if value is not None:
            query = query.filter(column == value)

    requested_work_type = work_type if work_type is not None else category
    if requested_work_type is not None:
        query = query.filter(Project.work_type == requested_work_type)

    return query.order_by(Project.project_id).offset(skip).limit(limit).all()


@router.get("/risk/{project_id:path}", response_model=ProjectRiskOut)
@router.get("/{project_id:path}/risk", response_model=ProjectRiskOut)
def get_project_risk_endpoint(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return the Phase 9 Risk Fusion record for a project, if one exists."""
    authorize_project_access(current_user, project_id, db)
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )

    risk = get_project_risk(db, project_id)
    if risk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Risk data for project '{project_id}' not found",
        )
    return ProjectRiskOut(**risk)


@router.get("/{project_id:path}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Return a single project by its project_id, or 404 if not found."""
    authorize_project_access(current_user, project_id, db)
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )
    return project