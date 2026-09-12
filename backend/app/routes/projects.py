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

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import Project
from app.schemas import ProjectOut, RiskFusionOut
from app.services.ml_service import get_risk_fusion_result

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
    return (
        db.query(Project)
        .order_by(Project.project_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/{project_id:path}/risk", response_model=RiskFusionOut)
def get_project_risk(project_id: str, db: Session = Depends(get_db)):
    """Return the current Phase 9 result for an existing project.

    The legacy Phase 2 fields remain available on ``GET /projects/{id}``
    for compatibility. This endpoint is the explicit current Risk Fusion
    contract and never falls back to those legacy values.
    """
    project = db.query(Project.project_id).filter(Project.project_id == project_id).first()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )
    result = get_risk_fusion_result(project_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Current Risk Fusion result for project '{project_id}' is not available",
        )
    return result


@router.get("/{project_id:path}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)):
    """Return a single project by its project_id, or 404 if not found."""
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )
    return project