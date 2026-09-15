"""
Shared SQL aggregation helpers over the `projects` table.

Phase 4 extraction: app/routes/dashboard.py originally computed all of
its aggregates inline. GET /analytics (Phase 4) needs several of the
same aggregates (core totals, risk_level_counts, by_state, by_work_type)
plus some new ones. Per the "no duplication" rule, the shared aggregates
were moved here so both routes call the exact same query logic instead
of two copies that could quietly drift apart. app/routes/dashboard.py's
response is unchanged -- these functions return the same values it
always computed, just from a shared location.

Every function here does its aggregation in SQL (COUNT/SUM/AVG/MIN/MAX/
GROUP BY) via SQLAlchemy -- none of them pull the 56,323-row `projects`
table into Python and aggregate there.

NULL handling, consistent throughout:
    - SQL AVG/MIN/MAX/COUNT(column) already ignore NULL rows for that
      column -- exactly the behavior wanted here (a project with no
      estimated_cost shouldn't drag the average toward zero or count as
      a min/max candidate). No manual NULL-filtering is needed for those.
    - Grouped fields (state, work_type, status) fold NULL/blank into an
      explicit "Not specified" bucket rather than dropping those projects
      from the total, so grouped counts still reconcile with
      total_projects.
    - risk_level is the one exception: a NULL risk_level means "not yet
      scored," which is not one of LOW/MEDIUM/HIGH/CRITICAL, so those
      rows are excluded from risk_level_counts entirely rather than
      folded into a bucket -- consistent with how dashboard.py already
      treated this before the Phase 4 extraction.
"""

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models import Project
from app.schemas import ByStateStat, ByWorkTypeStat, StatusCount


def _canonical_state_label(value):
    if value is None:
        return "Not specified"
    normalized = str(value).strip()
    return normalized if normalized else "Not specified"


def _canonical_work_type_label(value):
    if value is None:
        return "Not specified"
    normalized = str(value).strip()
    return normalized if normalized else "Not specified"


def _canonical_status_label(value):
    if value is None:
        return "Not specified"
    normalized = str(value).strip()
    if not normalized:
        return "Not specified"
    if normalized.lower() == "not specified":
        return "Not specified"
    return normalized.title()


def _canonical_risk_label(value):
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized.upper()


def compute_core_totals(db: Session) -> dict:
    """Project counts, financial totals, and progress averages.

    Moved verbatim from app/routes/dashboard.py's get_dashboard_stats --
    see that module's docstring for the completed/active/delayed status
    rule (unchanged by this extraction).
    """
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

    completed_projects = (
        db.query(func.count(Project.project_id))
        .filter(func.lower(func.trim(Project.status)) == "completed")
        .scalar()
    )
    active_projects = total_projects - completed_projects

    delayed_projects = (
        db.query(func.count(Project.project_id))
        .filter(
            func.lower(func.trim(Project.status)) != "completed",
            Project.expected_completion.isnot(None),
            Project.expected_completion < func.current_date(),
        )
        .scalar()
    )

    return {
        "total_projects": total_projects,
        "total_sanctioned_amount": total_sanctioned_amount,
        "total_expenditure": total_expenditure,
        "average_financial_progress": average_financial_progress,
        "average_physical_progress": average_physical_progress,
        "active_projects": active_projects,
        "completed_projects": completed_projects,
        "delayed_projects": delayed_projects,
    }


def compute_risk_level_counts(db: Session) -> dict[str, int]:
    """GROUP BY count of Project.risk_level. NULL/blank values are
    ignored and whitespace/case differences are normalized before
    bucketing."""
    normalized_risk_level = func.lower(func.trim(Project.risk_level))
    rows = (
        db.query(normalized_risk_level.label("risk_level_key"), func.count(Project.project_id))
        .filter(func.trim(Project.risk_level).isnot(None), func.trim(Project.risk_level) != "")
        .group_by(normalized_risk_level)
        .all()
    )
    return {_canonical_risk_label(level): count for level, count in rows if _canonical_risk_label(level) is not None}


def compute_by_state(db: Session) -> list[ByStateStat]:
    """Sanctioned/expenditure totals grouped by state. NULL/blank values
    are folded into "Not specified" and spacing/case variants are merged
    into a single bucket."""
    state_bucket = func.coalesce(func.nullif(func.trim(Project.state), ""), "Not specified")
    state_key = func.lower(state_bucket)
    rows = (
        db.query(
            state_key.label("state_key"),
            func.max(state_bucket).label("state"),
            func.coalesce(func.sum(Project.sanctioned_amount), 0),
            func.coalesce(func.sum(Project.expenditure), 0),
        )
        .group_by(state_key)
        .order_by(desc(func.coalesce(func.sum(Project.expenditure), 0)))
        .all()
    )
    return [
        ByStateStat(
            state=_canonical_state_label(state),
            total_sanctioned_amount=sanctioned,
            total_expenditure=expenditure,
        )
        for _, state, sanctioned, expenditure in rows
    ]


def compute_by_work_type(db: Session) -> list[ByWorkTypeStat]:
    """Project count grouped by work_type. NULL and blank/whitespace-only
    work_type are both folded into "Not specified" and equivalent values
    are merged regardless of case/spacing."""
    work_type_bucket = func.coalesce(func.nullif(func.trim(Project.work_type), ""), "Not specified")
    work_type_key = func.lower(work_type_bucket)
    rows = (
        db.query(
            work_type_key.label("work_type_key"),
            func.max(work_type_bucket).label("work_type"),
            func.count(Project.project_id),
        )
        .group_by(work_type_key)
        .order_by(desc(func.count(Project.project_id)))
        .all()
    )
    return [
        ByWorkTypeStat(work_type=_canonical_work_type_label(work_type), count=count)
        for _, work_type, count in rows
    ]


def compute_status_distribution(db: Session) -> list[StatusCount]:
    """Project count grouped by status. NULL/blank status is folded into
    "Not specified" and equivalent values are merged regardless of case or
    surrounding whitespace."""
    status_bucket = func.coalesce(func.nullif(func.trim(Project.status), ""), "Not specified")
    status_key = func.lower(status_bucket)
    rows = (
        db.query(
            status_key.label("status_key"),
            func.max(status_bucket).label("status"),
            func.count(Project.project_id),
        )
        .group_by(status_key)
        .order_by(desc(func.count(Project.project_id)))
        .all()
    )
    return [
        StatusCount(status=_canonical_status_label(status), count=count)
        for _, status, count in rows
    ]


def compute_risk_score_summary(db: Session) -> dict:
    """Average/min/max of Project.risk_score, plus how many projects
    actually have a (non-NULL) score. COUNT(risk_score) -- as opposed to
    COUNT(*) -- already skips NULL rows in SQL, so this is exactly the
    "how many were actually scored" count, not the full table size."""
    average, minimum, maximum, scored_count = db.query(
        func.avg(Project.risk_score),
        func.min(Project.risk_score),
        func.max(Project.risk_score),
        func.count(Project.risk_score),
    ).one()
    return {
        "average": average,
        "minimum": minimum,
        "maximum": maximum,
        "scored_project_count": scored_count,
    }


def compute_estimated_cost_summary(db: Session) -> dict:
    """Sum/average/min/max of Project.estimated_cost, plus how many
    projects actually have a value for it. Real Phase 2 rows have no
    source value for estimated_cost at all (see app/models.py /
    import_phase2.py) -- so on the real dataset,
    project_count_with_data will legitimately be 0 or close to it, and
    the other fields will be null. This is reported explicitly rather
    than silently defaulted to 0."""
    total, average, minimum, maximum, count_with_data = db.query(
        func.sum(Project.estimated_cost),
        func.avg(Project.estimated_cost),
        func.min(Project.estimated_cost),
        func.max(Project.estimated_cost),
        func.count(Project.estimated_cost),
    ).one()
    return {
        "total": total,
        "average": average,
        "minimum": minimum,
        "maximum": maximum,
        "project_count_with_data": count_with_data,
    }


def compute_progress_summary(db: Session, column) -> dict:
    """Average/min/max for a progress column (financial_progress or
    physical_progress), plus how many projects have a value for it.
    Generic over `column` so the same query logic backs both fields
    instead of two near-identical copies."""
    average, minimum, maximum, count_with_data = db.query(
        func.avg(column),
        func.min(column),
        func.max(column),
        func.count(column),
    ).one()
    return {
        "average": average,
        "minimum": minimum,
        "maximum": maximum,
        "project_count_with_data": count_with_data,
    }