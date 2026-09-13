"""Anonymous, public-safe national Overview data."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.aggregations import (
    compute_by_state,
    compute_core_totals,
    compute_risk_level_counts,
    compute_status_distribution,
)
from app.database import get_db
from app.models import Project
from app.schemas import PublicOverview, PublicProjectOut

router = APIRouter(prefix="/public", tags=["public"])


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
        status_distribution=status_distribution,
        recent_projects=[PublicProjectOut.model_validate(project) for project in projects],
    )