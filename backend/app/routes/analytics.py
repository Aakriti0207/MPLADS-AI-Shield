"""
Route for GET /analytics.

Phase 4: a dedicated, more complete analytics contract for the project
portfolio. No dedicated /analytics endpoint existed before this file --
verified by inspecting app/main.py's registered routers and the rest of
app/routes/ (Phase 1/2/3 audits reached the same conclusion; the
frontend's Analytics.jsx page has instead been using GET /dashboard/stats,
which remains available and unchanged).

This route follows the exact same conventions as the other protected
routes (projects.py, dashboard.py, alerts.py): router-level
Depends(get_current_user), a Session from get_db, and a typed
response_model. It reuses app/aggregations.py's query functions rather
than recomputing anything dashboard.py already computes correctly, so
GET /dashboard/stats and GET /analytics can never quietly disagree on
the fields they share (total_projects, risk_level_counts, by_state,
by_work_type, etc).

Every aggregate here is computed with SQL COUNT/SUM/AVG/MIN/MAX/GROUP BY
-- the 56,323-row `projects` table is never loaded into Python to be
summarized there. See app/aggregations.py's module docstring for the
NULL-handling rules applied throughout.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.aggregations import (
    compute_by_state,
    compute_by_work_type,
    compute_core_totals,
    compute_estimated_cost_summary,
    compute_progress_summary,
    compute_risk_level_counts,
    compute_risk_score_summary,
    compute_status_distribution,
)
from app.database import get_db
from app.auth import get_current_user
from app.models import Project
from app.schemas import (
    AnalyticsResponse,
    EstimatedCostSummary,
    ProgressSummary,
    RiskScoreSummary,
)

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=AnalyticsResponse)
def get_analytics(db: Session = Depends(get_db)):
    """
    Return the full Phase 4 analytics contract, computed live from the
    `projects` table.

    Shares its core totals, risk_level_counts, by_state, and
    by_work_type fields with GET /dashboard/stats (same underlying
    aggregation functions -- see app/aggregations.py); adds a risk-score
    summary, an estimated-cost summary, financial/physical progress
    summaries, and a status distribution on top.
    """
    totals = compute_core_totals(db)
    risk_level_counts = compute_risk_level_counts(db)
    by_state = compute_by_state(db)
    by_work_type = compute_by_work_type(db)

    risk_score_summary = RiskScoreSummary(**compute_risk_score_summary(db))
    estimated_cost_summary = EstimatedCostSummary(**compute_estimated_cost_summary(db))
    financial_progress_summary = ProgressSummary(
        **compute_progress_summary(db, Project.financial_progress)
    )
    physical_progress_summary = ProgressSummary(
        **compute_progress_summary(db, Project.physical_progress)
    )
    status_distribution = compute_status_distribution(db)

    return AnalyticsResponse(
        **totals,
        risk_level_counts=risk_level_counts,
        by_state=by_state,
        by_work_type=by_work_type,
        risk_score_summary=risk_score_summary,
        estimated_cost_summary=estimated_cost_summary,
        financial_progress_summary=financial_progress_summary,
        physical_progress_summary=physical_progress_summary,
        status_distribution=status_distribution,
    )