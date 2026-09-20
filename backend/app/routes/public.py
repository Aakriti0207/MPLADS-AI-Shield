"""Anonymous, public-safe MPLADS data.

Phase 5 (Public Dashboard Overhaul)
-----------------------------------
This module is the ONLY anonymous surface of the application, so it is
deliberately kept free of every risk/AI/investigation concept:

    no risk_score            no financial anomaly score
    no risk_level            no payment anomaly score
    no Risk Fusion output    no timeline anomaly score
    no AI reasoning          no duplicate score
    no alerts                no isolation-forest score
    no review/investigation  no internal/admin notes

Three things changed here in Phase 5:

1.  `GET /public/overview` no longer returns `risk_level_counts`. That
    field was the last risk-derived value on the public contract and it
    fed the Overview page's "Requiring Review" KPI.

2.  `GET /public/insights` (+ `/public/insights/districts`) were added.
    They are built on `app/public_aggregations.py` -- a dedicated public
    aggregation layer over the canonical dataset -- rather than on the
    authenticated, risk-aware `DashboardStats` contract, so the public
    and internal data paths are separated structurally.

3.  `GET /public/overview`'s AGGREGATE fields (totals, by_state,
    by_work_type, status_distribution) now come from the SAME canonical
    frame as `/public/insights`, instead of the legacy `Project` DB
    table. See the "Canonical public data source" note on
    `get_public_overview()` below for why this was necessary and what
    is deliberately left unchanged.

`GET /public/projects` and `GET /public/projects/{id}` are unchanged and
still serve `PublicProjectOut` from the project database.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.geo_centroids import resolve_coordinates
from app.models import Project
from app.public_aggregations import (
    compute_category_breakdown,
    compute_completion_trend,
    compute_data_coverage,
    compute_district_insights,
    compute_expenditure_trend,
    compute_public_kpis,
    compute_recent_public_projects,
    compute_sanction_trend,
    compute_state_insights,
    compute_status_distribution as compute_public_status_distribution,
    filter_frame,
    load_public_frame,
)
from app.schemas import (
    ByStateStat,
    ByWorkTypeStat,
    PublicDistrictResponse,
    PublicInsights,
    PublicOverview,
    PublicProjectOut,
    PublicProjectPage,
    StatusCount,
)

router = APIRouter(prefix="/public", tags=["public"])


PUBLIC_DISCLAIMER = (
    "Aggregated from published MPLADS records for public transparency. "
    "Figures reflect what the source dataset records; fields with no "
    "recorded value are reported as unavailable rather than estimated."
)


def _public_project_out(project: Project) -> PublicProjectOut:
    """
    Build a PublicProjectOut from a DB `Project` row, with the same
    documented district/state-centroid coordinate fallback the
    protected and demo project APIs use (app/geo_centroids.py), so all
    three surfaces answer the Map feature consistently. `Project.
    latitude`/`longitude` are read here (via model_validate) but are
    NULL for essentially every row -- see app/models.py's Phase 2
    docstring -- so they are overwritten with the resolved fallback,
    never left silently blank while the other two APIs show a point.
    """
    public_project = PublicProjectOut.model_validate(project)
    latitude, longitude, location_precision = resolve_coordinates(
        project.state,
        project.district,
    )
    return public_project.model_copy(
        update={
            "latitude": latitude,
            "longitude": longitude,
            "location_precision": location_precision,
        }
    )


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
        items=[_public_project_out(project) for project in items],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/projects/{project_id:path}", response_model=PublicProjectOut)
def get_public_project(project_id: str, db: Session = Depends(get_db)):
    """Anonymous-safe project detail for a single project.

    Serves the Overview page's "Recently Monitored Projects" click-through
    (and any other public deep link to a project) without requiring a
    session. Deliberately reuses `PublicProjectOut` -- the exact same
    sanitized field set already returned by `GET /public/projects` -- so
    this can never leak anything `list_public_projects` doesn't already
    expose: no risk_score, risk_level, risk reasons, review/internal
    notes, or auth/user data. `GET /projects/{id}` (protected, full
    `ProjectOut`) is untouched and keeps requiring authentication.
    """
    project = db.query(Project).filter(Project.project_id == project_id).first()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )
    return _public_project_out(project)


@router.get("/overview", response_model=PublicOverview)
def get_public_overview(
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Return national aggregates and limited public project summaries.

    This route intentionally does not expose ProjectOut or any risk
    details. Phase 5 removed `risk_level_counts` from the response (and
    from `PublicOverview`); the richer public dashboard data now lives on
    `GET /public/insights`.

    Canonical public data source (verification-pass fix)
    ------------------------------------------------------
    Before this fix, this route's totals/by_state/by_work_type/
    status_distribution were computed over the legacy `Project` DB table
    (`app.aggregations.compute_core_totals` and friends), while
    `GET /public/insights` computed the same-shaped figures over
    `canonical_projects.csv` (43,863 projects, via
    `app/public_aggregations.py`). Those are two DIFFERENT project
    universes -- in this checkout's own data, the `Project` table's usual
    source (`data/phase2/project_risk_scores.csv`) has 56,323 rows and
    only ~35,656 of those `work_id`s overlap with the canonical 43,863 --
    so the two public endpoints could legitimately report different
    totals, state lists and category breakdowns for what a visitor would
    reasonably expect to be "the same" public dashboard. `Projects.jsx`
    and `Dashboard.jsx`'s anonymous-fallback path both consume this
    route's `by_state`/`by_work_type` for filter options, so this was a
    live inconsistency risk, not just a hypothetical one.

    This route's aggregate fields now call the SAME functions
    `GET /public/insights` uses (`compute_public_kpis`,
    `compute_state_insights`, `compute_category_breakdown`,
    `compute_status_distribution`), so the two endpoints can never
    disagree on a national total, a state's figures, or a category count.

    `recent_projects` deliberately STAYS on the `Project` DB table. Two
    reasons, both hard constraints, not preferences:
      1. `GET /public/projects/{id}` (the public project-detail route)
         is, and must remain, DB-backed -- switching `recent_projects` to
         canonical would link to `work_id`s the detail route can't find
         (the canonical-only ~8,207 projects aren't in the DB table),
         producing dead 404 links from the Overview's "Recently
         Monitored Projects" table.
      2. `tests/test_public_project_detail.py::
         test_public_overview_recent_projects_carry_a_usable_project_id`
         seeds a DB-only project and asserts this route's
         `recent_projects[0]` resolves through `/public/projects/{id}`;
         that is only possible when both stay on the same (DB) source.
    This means `/public/overview`'s aggregates and its `recent_projects`
    list now come from two different sources within one response. That
    split is real and is called out as a known remaining item in the
    Phase 5 verification report -- it is the smallest change that fixes
    the cross-endpoint inconsistency without breaking the project-detail
    contract or its existing tests.

    `average_financial_progress` is reported as the portfolio-level
    expenditure/sanctioned ratio (same figure `/public/insights` exposes
    as `expenditure_utilisation_percent`) rather than a per-project
    average, because the canonical frame is the source now and that is
    the only honest "financial progress" figure it supports.
    `delayed_projects` is reported as `None`: the canonical dataset has
    no expected/target completion date, so there is no source data to
    compute a delay count from -- reporting 0 would incorrectly imply
    "no projects delayed" rather than "not measurable".

    The project rows are ordered by the stored update timestamp, with the
    project id as a deterministic tie-breaker.
    """
    try:
        frame = load_public_frame()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Public project dataset is unavailable: {exc}",
        ) from exc

    kpis = compute_public_kpis(frame)

    projects = (
        db.query(Project)
        .order_by(Project.updated_at.desc(), Project.project_id)
        .limit(limit)
        .all()
    )

    return PublicOverview(
        total_projects=kpis["total_projects"],
        total_sanctioned_amount=kpis["total_sanctioned_amount"],
        total_expenditure=kpis["total_expenditure"],
        average_financial_progress=kpis["expenditure_utilisation_percent"],
        completed_projects=kpis["completed_projects"],
        active_projects=kpis["active_works"],
        delayed_projects=None,
        by_state=[
            ByStateStat(
                state=row["state"],
                total_sanctioned_amount=row["total_sanctioned_amount"],
                total_expenditure=row["total_expenditure"],
            )
            for row in compute_state_insights(frame)
        ],
        by_work_type=[
            ByWorkTypeStat(work_type=row["work_type"], count=row["count"])
            for row in compute_category_breakdown(frame)
        ],
        status_distribution=[
            StatusCount(status=row["status"], count=row["count"])
            for row in compute_public_status_distribution(frame)
        ],
        recent_projects=[_public_project_out(project) for project in projects],
    )


@router.get("/insights", response_model=PublicInsights)
def get_public_insights(
    state: str | None = Query(
        None,
        max_length=120,
        description="Optional state filter. Narrows every figure in the response.",
    ),
    district: str | None = Query(
        None,
        max_length=120,
        description="Optional district filter, applied within `state`.",
    ),
    recent_limit: int = Query(8, ge=1, le=25),
    top_categories: int = Query(12, ge=1, le=50),
):
    """Public dashboard data: KPIs, real trends, state/district insights.

    Sourced entirely from the canonical project dataset via
    `app/public_aggregations.py`, so every figure -- national, state or
    district -- is derived from the same canonical `work_id` universe the
    authenticated views use. No database session is required and no
    authentication is involved.

    `state`/`district` narrow the WHOLE payload, which is what powers the
    State -> District drilldown on the Overview page.
    """
    try:
        frame = load_public_frame()
    except (FileNotFoundError, ValueError) as exc:
        # The canonical dataset is a build artefact of the ML pipeline. If
        # it is missing we say so explicitly rather than serving zeros
        # that would read as "no MPLADS activity".
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Public project dataset is unavailable: {exc}",
        ) from exc

    if district and not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="`district` requires `state` so the drilldown is unambiguous.",
        )

    scoped = filter_frame(frame, state=state, district=district)

    if (state or district) and scoped.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No public projects found for the requested area.",
        )

    return PublicInsights(
        kpis=compute_public_kpis(scoped),
        trends={
            "expenditure": compute_expenditure_trend(scoped),
            "completion": compute_completion_trend(scoped),
            "sanction": compute_sanction_trend(scoped),
        },
        # `by_state` always reflects the requested scope: unscoped it is
        # the national picture, scoped it is the single selected state.
        by_state=compute_state_insights(scoped),
        # District rows are returned only for a scoped request. The
        # national district list is ~815 rows / ~220 KB, which would
        # dominate a payload that the Overview page loads on first paint
        # and does not use until a state is selected. Callers that want
        # every district can use GET /public/insights/districts, which
        # serves exactly that list.
        by_district=(
            compute_district_insights(scoped, state=state) if state else []
        ),
        by_work_type=compute_category_breakdown(scoped, limit=top_categories),
        status_distribution=compute_public_status_distribution(scoped),
        recent_projects=compute_recent_public_projects(scoped, limit=recent_limit),
        data_coverage=compute_data_coverage(scoped),
        disclaimer=PUBLIC_DISCLAIMER,
    )


@router.get("/insights/districts", response_model=PublicDistrictResponse)
def get_public_districts(
    state: str | None = Query(
        None,
        max_length=120,
        description="State to drill into. Omit for every district nationally.",
    ),
):
    """District-level public aggregates for the State -> District drilldown.

    Split out from `/public/insights` so selecting a state on the Overview
    map fetches only the district table instead of recomputing the whole
    national payload.
    """
    try:
        frame = load_public_frame()
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Public project dataset is unavailable: {exc}",
        ) from exc

    districts = compute_district_insights(frame, state=state)

    if state and not districts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No public projects found for state '{state}'.",
        )

    return PublicDistrictResponse(state=state, districts=districts)