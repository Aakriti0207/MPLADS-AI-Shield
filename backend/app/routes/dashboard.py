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

Phase 4 update: the actual aggregation queries were extracted to
app/aggregations.py so GET /analytics can reuse the exact same logic
instead of a second, potentially-drifting copy. This route's behavior
and response shape are UNCHANGED by that extraction -- it computes and
returns exactly what it always did.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.aggregations import (
    compute_by_state,
    compute_by_work_type,
    compute_core_totals,
    compute_risk_level_counts,
)
from app.database import get_db
from app.auth import get_current_user
from app.schemas import DashboardStats

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    totals = compute_core_totals(db)
    risk_level_counts = compute_risk_level_counts(db)
    by_state = compute_by_state(db)
    by_work_type = compute_by_work_type(db)

    return DashboardStats(
        **totals,
        risk_level_counts=risk_level_counts,
        by_state=by_state,
        by_work_type=by_work_type,
    )