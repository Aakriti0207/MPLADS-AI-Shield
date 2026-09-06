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
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import Project
from app.schemas import ByStateStat, ByWorkTypeStat, DashboardStats

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)


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

    # --- Phase 3C: real risk_level breakdown for the Dashboard's risk
    # overview card. Straight GROUP BY count over the existing Phase 2
    # risk_level column -- no new table, no change to how risk_level is
    # calculated. A NULL risk_level (project not yet scored) is dropped
    # rather than counted under any bucket, since it isn't one of
    # LOW/MEDIUM/HIGH/CRITICAL.
    risk_level_rows = (
        db.query(Project.risk_level, func.count(Project.project_id))
        .group_by(Project.risk_level)
        .all()
    )
    risk_level_counts = {
        level: count for level, count in risk_level_rows if level is not None
    }

    # --- Phase 3E: state-level financial aggregate for Analytics. ---
    # NULL state (real for ~41% of Phase 2 rows) is grouped under
    # "Not specified" rather than dropped, so the totals still reconcile
    # with total_sanctioned_amount/total_expenditure above. Sorted by
    # expenditure desc so the frontend can take a straightforward top-N.
    state_label = func.coalesce(Project.state, "Not specified")
    state_rows = (
        db.query(
            state_label.label("state"),
            func.coalesce(func.sum(Project.sanctioned_amount), 0),
            func.coalesce(func.sum(Project.expenditure), 0),
        )
        .group_by(state_label)
        .order_by(desc(func.coalesce(func.sum(Project.expenditure), 0)))
        .all()
    )
    by_state = [
        ByStateStat(state=state, total_sanctioned_amount=sanctioned, total_expenditure=expenditure)
        for state, sanctioned, expenditure in state_rows
    ]

    # --- Phase 3E: work-type breakdown for Analytics. ---
    # NULL and blank/whitespace-only work_type are both folded into
    # "Not specified" (real Phase 2 rows can have either). Sorted by
    # count desc so the frontend can take a top-N + "Other" straightforwardly.
    work_type_label = func.coalesce(func.nullif(func.trim(Project.work_type), ""), "Not specified")
    work_type_rows = (
        db.query(work_type_label.label("work_type"), func.count(Project.project_id))
        .group_by(work_type_label)
        .order_by(desc(func.count(Project.project_id)))
        .all()
    )
    by_work_type = [
        ByWorkTypeStat(work_type=work_type, count=count)
        for work_type, count in work_type_rows
    ]

    return DashboardStats(
        total_projects=total_projects,
        total_sanctioned_amount=total_sanctioned_amount,
        total_expenditure=total_expenditure,
        average_financial_progress=average_financial_progress,
        average_physical_progress=average_physical_progress,
        active_projects=active_projects,
        completed_projects=completed_projects,
        delayed_projects=delayed_projects,
        risk_level_counts=risk_level_counts,
        by_state=by_state,
        by_work_type=by_work_type,
    )