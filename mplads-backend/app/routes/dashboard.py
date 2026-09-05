"""
Routes for dashboard-level aggregate statistics.

All numbers are computed live from the `projects` table via SQLAlchemy
aggregate queries - nothing here is hardcoded or cached.

Status/date rule used consistently throughout this module:
    - `status` is treated as the authoritative field for whether a
      project is "completed". A project is completed when
      status = 'Completed' (case-insensitive).
    - "Active" simply means "not completed yet" - i.e. every project
      that hasn't been marked Completed (Sanctioned, Ongoing, Delayed,
      or any other in-progress status all count as active). This keeps
      active + completed always summing to total_projects, without
      hardcoding every possible status string that might appear in the
      source data.
    - "Delayed" is a date-driven refinement of "active": an active
      (not-yet-completed) project is delayed when it has an
      expected_completion date and that date has already passed
      (expected_completion < today). This combines the status field
      (to exclude anything already completed) with the date field (to
      judge lateness), rather than inventing a separate "Delayed"
      status string that may or may not exist in the source data.
      Projects with no expected_completion date are never counted as
      delayed, since there's no deadline to have missed.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project
from app.schemas import DashboardStats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    # --- Core totals & averages in a single aggregate query ---
    totals = db.query(
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

    # --- Completed vs. active, based on status (see module docstring) ---
    completed_projects = (
        db.query(func.count(Project.project_id))
        .filter(func.lower(Project.status) == "completed")
        .scalar()
    )
    active_projects = total_projects - completed_projects

    # --- Delayed: active projects whose expected_completion has passed ---
    delayed_projects = (
        db.query(func.count(Project.project_id))
        .filter(
            func.lower(Project.status) != "completed",
            Project.expected_completion.isnot(None),
            Project.expected_completion < func.current_date(),
        )
        .scalar()
    )

    return DashboardStats(
        total_projects=total_projects,
        total_sanctioned_amount=total_sanctioned_amount,
        total_expenditure=total_expenditure,
        average_financial_progress=average_financial_progress,
        average_physical_progress=average_physical_progress,
        active_projects=active_projects,
        completed_projects=completed_projects,
        delayed_projects=delayed_projects,
    )
