"""Anonymous, citizen-facing project explorer routes.

Every route below is served from the canonical public frame through
`app/public_explorer.py` and returns only explicit allowlist models.
See that module's docstring for the safety rules. No authentication is
required and none of these routes read Risk Fusion or any risk column.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app import public_explorer as explorer
from app.public_explorer import (
    PublicAreaResponse,
    PublicFilterOptions,
    PublicMeta,
    PublicProjectDetail,
    PublicProjectResults,
    PublicSummary,
)
from app.public_aggregations import load_public_frame

router = APIRouter(prefix="/public", tags=["public-explorer"])


def _dataset_unavailable(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Public project data is temporarily unavailable.",
    )


@router.get("/explorer/projects", response_model=PublicProjectResults)
def explorer_projects(
    search: Optional[str] = Query(None, max_length=120),
    state: Optional[str] = Query(None, max_length=120),
    district: Optional[str] = Query(None, max_length=120),
    category: Optional[str] = Query(None, max_length=120),
    status_value: Optional[str] = Query(None, alias="status", max_length=60),
    year: Optional[int] = Query(None, ge=1990, le=2100, description="Sanction year"),
    detailed: bool = Query(False, description="Only projects with a description and a sanctioned amount"),
    sort: str = Query("recent", pattern="^(recent|sanctioned_desc|expenditure_desc)$"),
    page: int = Query(1, ge=1, le=100000),
    page_size: int = Query(20, ge=1, le=50),
):
    """Search + filter + paginate public projects (server-side)."""
    if district and not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="`district` requires `state`.",
        )
    try:
        return explorer.query_projects(
            page=page,
            page_size=page_size,
            sort=sort,
            search=search,
            state=state,
            district=district,
            category=category,
            status=status_value,
            year=year,
            detailed=detailed,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise _dataset_unavailable(exc) from exc


@router.get("/explorer/projects/{project_id:path}", response_model=PublicProjectDetail)
def explorer_project_detail(project_id: str):
    """One public project by canonical project id."""
    try:
        project = explorer.get_project(project_id)
    except (FileNotFoundError, ValueError) as exc:
        raise _dataset_unavailable(exc) from exc

    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return project


@router.get("/explorer/filters", response_model=PublicFilterOptions)
def explorer_filters(state: Optional[str] = Query(None, max_length=120)):
    """Filter options that exist in the data. Districts need a state."""
    try:
        return explorer.filter_options(state=state)
    except (FileNotFoundError, ValueError) as exc:
        raise _dataset_unavailable(exc) from exc


@router.get("/explorer/areas", response_model=PublicAreaResponse)
def explorer_areas(
    state: Optional[str] = Query(None, max_length=120),
    category: Optional[str] = Query(None, max_length=120),
    status_value: Optional[str] = Query(None, alias="status", max_length=60),
):
    """State rows (or district rows when `state` is set) for the map and
    drill-down, narrowed by optional category / status filters."""
    try:
        result = explorer.area_breakdown(
            state=state, category=category, status=status_value
        )
    except (FileNotFoundError, ValueError) as exc:
        raise _dataset_unavailable(exc) from exc

    if state and not result.rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No public projects found for that state.",
        )
    return result


@router.get("/explorer/summary", response_model=PublicSummary)
def explorer_summary(
    state: Optional[str] = Query(None, max_length=120),
    district: Optional[str] = Query(None, max_length=120),
):
    """National (or state / district) totals, status and category mix."""
    if district and not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="`district` requires `state`.",
        )
    try:
        summary = explorer.build_summary(state=state, district=district)
    except (FileNotFoundError, ValueError) as exc:
        raise _dataset_unavailable(exc) from exc

    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No public projects found for the requested area.",
        )
    return summary


@router.get("/meta", response_model=PublicMeta)
def public_meta():
    """Data freshness and source description."""
    try:
        return explorer.build_meta(load_public_frame())
    except (FileNotFoundError, ValueError) as exc:
        raise _dataset_unavailable(exc) from exc