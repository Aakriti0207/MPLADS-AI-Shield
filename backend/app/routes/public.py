"""Anonymous, public-safe national Overview data."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.aggregations import (
    compute_by_state,
    compute_by_work_type,
    compute_core_totals,
    compute_risk_level_counts,
    compute_status_distribution,
)
from app.database import get_db
from app.models import Project
from app.schemas import PublicOverview, PublicProjectOut, PublicProjectPage

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/projects", response_model=PublicProjectPage)
def list_public_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    state: str | None = Query(None),
    category: str | None = Query(None),
    status_value: str | None = Query(None, alias="status"),
    search: str | None = Query(None, max_length=120),
    db: Session = Depends(get_db),
):
    """Browse real projects with only fields intended for public viewing."""
    query = db.query(Project)
    if state:
        query = query.filter(Project.state == state)
    if category:
        query = query.filter(Project.work_type == category)
    if status_value:
        query = query.filter(Project.status == status_value)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(
            Project.project_id.ilike(pattern),
            Project.state.ilike(pattern),
            Project.constituency.ilike(pattern),
            Project.work_type.ilike(pattern),
            Project.mp_name.ilike(pattern),
        ))
    total = query.count()
    items = query.order_by(Project.project_id).offset(skip).limit(limit).all()
    return PublicProjectPage(
        items=[PublicProjectOut.model_validate(project) for project in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/projects/{project_id:path}", response_model=PublicProjectOut)
def get_public_project(project_id: str, db: Session = Depends(get_db)):
    """Anonymous-safe single-project detail lookup.

    Added so the public Overview's "Recently Monitored Projects" list
    (and the public /projects explorer) can link to a project detail
    page without requiring a session. This deliberately reuses
    PublicProjectOut -- the same sanitized shape already used by
    list_public_projects/get_public_overview above -- so this route
    can never leak risk_score, risk_level, risk reasons, internal
    review/anomaly notes, or any stakeholder/user data: those fields
    simply are not on PublicProjectOut. `GET /projects/{id}` (in
    routes/projects.py) is untouched and still requires
    authentication for the full, risk-inclusive record.
    """
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )
    return project


@router.get("/overview", response_model=PublicOverview)
def get_public_overview(
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Return national aggregates and limited public project summaries.

    This route intentionally does not expose ProjectOut or any risk details.
    The project rows are ordered by the stored update timestamp, with the
    project id as a deterministic tie-breaker.
    """
    totals = compute_core_totals(db)
    projects = (
        db.query(Project)
        .order_by(Project.updated_at.desc(), Project.project_id)
        .limit(limit)
        .all()
    )
    status_distribution = compute_status_distribution(db)
    has_explicit_status = any(row.status != "Not specified" for row in status_distribution)
    return PublicOverview(
        total_projects=totals["total_projects"],
        total_sanctioned_amount=totals["total_sanctioned_amount"],
        total_expenditure=totals["total_expenditure"],
        average_financial_progress=totals["average_financial_progress"],
        completed_projects=totals["completed_projects"] if has_explicit_status else None,
        active_projects=totals["active_projects"] if has_explicit_status else None,
        delayed_projects=totals["delayed_projects"] if has_explicit_status else None,
        risk_level_counts=compute_risk_level_counts(db),
        by_state=compute_by_state(db),
        by_work_type=compute_by_work_type(db),
        status_distribution=status_distribution,
        recent_projects=[PublicProjectOut.model_validate(project) for project in projects],
    )