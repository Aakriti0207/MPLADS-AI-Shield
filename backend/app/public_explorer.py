"""
Public Portal explorer layer (citizen-facing project browsing).

Why this module exists
----------------------
The original anonymous project routes (`GET /public/projects`,
`GET /public/projects/{id}`) read the legacy `Project` DB table. That
table is a DIFFERENT project universe from the canonical dataset that
every public aggregate (`/public/insights`, `/public/overview` totals)
is computed from, so a project counted on the dashboard could 404 on its
detail page, and the list could not be searched by project description
or filtered by district.

This module gives the public portal one consistent, canonical-backed
surface:

    canonical_projects.csv -> public_aggregations.load_public_frame()
                           -> public_explorer.py -> /public/explorer/*

Design rules
------------
* ALLOWLIST ONLY. Every response model below is an explicit field list.
  Nothing is serialised from a raw row, so a new column appearing in the
  canonical CSV can never reach an anonymous response.
* No risk / AI / anomaly / duplicate / isolation-forest / alert / review
  / investigation field is read, computed or returned here. This module
  never imports Risk Fusion or `project_risk_scores`.
* The project id is the canonical `work_id` (unchanged).
* Missing data is `None`, never `0`, never a placeholder string.
* Existing `/public/*` routes are untouched, so existing clients and
  tests keep working.
"""

from __future__ import annotations

import math
import re
import threading
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd
from pydantic import BaseModel

from app.aggregations import CANONICAL_PROJECTS_PATH
from app.public_aggregations import (
    NOT_SPECIFIED,
    compute_public_kpis,
    compute_status_distribution,
    filter_frame,
    load_public_frame,
)
from app.schemas import PublicKpis, StatusCount

# ---------------------------------------------------------------------
# Public response models (explicit allowlists)
# ---------------------------------------------------------------------

SORT_OPTIONS = ("recent", "sanctioned_desc", "expenditure_desc")

MAX_SEARCH_TOKENS = 6
TITLE_MAX_CHARS = 140


class PublicProjectSummary(BaseModel):
    """Card / list-row fields. Nothing internal."""

    project_id: str
    title: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    constituency: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    sanctioned_amount: Optional[float] = None
    expenditure: Optional[float] = None
    utilisation_percent: Optional[float] = None
    sanction_date: Optional[str] = None
    completion_date: Optional[str] = None


class PublicProjectDetail(PublicProjectSummary):
    """Detail-page fields: the summary plus already-public record data."""

    description: Optional[str] = None
    mp_name: Optional[str] = None
    implementing_agency: Optional[str] = None
    recommended_amount: Optional[float] = None
    recommended_date: Optional[str] = None
    first_expenditure_date: Optional[str] = None
    last_expenditure_date: Optional[str] = None


class PublicProjectResults(BaseModel):
    items: list[PublicProjectSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class PublicMeta(BaseModel):
    """Freshness + provenance. Only values that really exist."""

    total_projects: int
    # File modification time of the canonical dataset the portal reads.
    dataset_refreshed_at: Optional[str] = None
    # Most recent date that appears in any public date column.
    latest_record_date: Optional[str] = None
    source_note: str


class FilterOption(BaseModel):
    value: str
    count: int


class PublicFilterOptions(BaseModel):
    states: list[FilterOption]
    districts: list[FilterOption]
    categories: list[FilterOption]
    statuses: list[FilterOption]
    # Sanction years that actually occur in the records.
    years: list[FilterOption]


class AreaRow(BaseModel):
    name: str
    state: Optional[str] = None
    project_count: int
    sanctioned_amount: float
    expenditure: float
    completed_projects: int
    ongoing_projects: int
    utilisation_percent: Optional[float] = None


class PublicAreaResponse(BaseModel):
    level: str  # "state" | "district"
    state: Optional[str] = None
    rows: list[AreaRow]


class SectorStat(BaseModel):
    category: str
    count: int
    total_sanctioned_amount: float
    total_expenditure: float


class UtilisationBasis(BaseModel):
    """Like-for-like utilisation.

    Expenditure is compared only with the sanctioned amount of projects
    that HAVE a recorded sanctioned amount. Comparing all expenditure
    with that (smaller) sanctioned total would overstate utilisation.
    """

    percent: Optional[float] = None
    projects_with_sanctioned_amount: int
    sanctioned_amount: float
    expenditure_on_those_projects: float
    projects_with_expenditure_record: int
    total_projects: int


class PublicSummary(BaseModel):
    scope_state: Optional[str] = None
    scope_district: Optional[str] = None
    kpis: PublicKpis
    utilisation: UtilisationBasis
    status_distribution: list[StatusCount]
    by_state: list[AreaRow]
    by_district: list[AreaRow]
    by_category: list[SectorStat]
    meta: PublicMeta


SOURCE_NOTE = (
    "Information shown here is aggregated from published MPLADS project "
    "records. Fields with no recorded value are shown as not available "
    "rather than estimated."
)

# ---------------------------------------------------------------------
# Prepared frame (search index + sort key), cached against the frame
# ---------------------------------------------------------------------

_PREPARED: dict[str, Any] = {"source": None, "frame": None}
# One build at a time: the first page load fires several requests at once
# (summary + projects + filters + meta). Without this lock each of them
# would parse the 43k-row dataset in parallel, which makes the cold start
# several times slower.
_BUILD_LOCK = threading.Lock()

_ESTIMATE_SUFFIX = re.compile(
    r"\s*\(\s*(?:estimated|est\.?)\b[^)]*\)\s*\.?\s*$", re.IGNORECASE
)
_NAN_YEARS = re.compile(r"\s*\(\s*NaN\s*-\s*NaN\s*\)", re.IGNORECASE)


def _text_col(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype="object")
    return frame[column].astype("object").where(frame[column].notna(), "").astype(str)


def prepared_frame() -> pd.DataFrame:
    """Public frame + lowercase search haystack + 'recent activity' key."""
    with _BUILD_LOCK:
        base = load_public_frame()

        if _PREPARED["source"] is base:
            return _PREPARED["frame"]

        work = base.copy()

        parts = [
            _text_col(work, "work_id"),
            _text_col(work, "work_description"),
            _text_col(work, "district_label"),
            _text_col(work, "state_label"),
            _text_col(work, "constituency"),
            _text_col(work, "sector_label"),
        ]
        haystack = parts[0]
        for part in parts[1:]:
            haystack = haystack + " | " + part
        work["_haystack"] = haystack.str.lower()

        work["_recent"] = (
            work["last_expenditure_date"]
            .fillna(work["completion_date"])
            .fillna(work["sanction_date"])
        )

        _PREPARED["source"] = base
        _PREPARED["frame"] = work
        return work


# ---------------------------------------------------------------------
# Small conversion helpers
# ---------------------------------------------------------------------

def _num(value: Any) -> Optional[float]:
    try:
        number = pd.to_numeric(value, errors="coerce")
    except (TypeError, ValueError):
        return None
    if number is None or pd.isna(number) or not math.isfinite(float(number)):
        return None
    return float(number)


def _iso(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    try:
        return value.date().isoformat()
    except AttributeError:
        return None


def _clean_text(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan" or text == NOT_SPECIFIED:
        return None
    return text


def _title_from_description(value: Any) -> Optional[str]:
    text = _clean_text(value)
    if text is None:
        return None
    text = _ESTIMATE_SUFFIX.sub("", " ".join(text.split())).strip()
    if not text:
        return None
    if len(text) > TITLE_MAX_CHARS:
        text = text[: TITLE_MAX_CHARS - 1].rstrip() + "\u2026"
    return text


def _utilisation(sanctioned: Optional[float], expenditure: Optional[float]) -> Optional[float]:
    if sanctioned is None or expenditure is None or sanctioned <= 0:
        return None
    return expenditure / sanctioned * 100


def _summary_dict(row: pd.Series) -> dict[str, Any]:
    sanctioned = _num(row.get("sanction_amount"))
    expenditure = _num(row.get("total_expenditure"))
    return {
        "project_id": str(row.get("work_id")),
        "title": _title_from_description(row.get("work_description")),
        "state": _clean_text(row.get("state_label")),
        "district": _clean_text(row.get("district_label")),
        "constituency": _clean_text(row.get("constituency")),
        "category": _clean_text(row.get("sector_label")),
        "status": _clean_text(row.get("status_label")),
        "sanctioned_amount": sanctioned,
        "expenditure": expenditure,
        "utilisation_percent": _utilisation(sanctioned, expenditure),
        "sanction_date": _iso(row.get("sanction_date")),
        "completion_date": _iso(row.get("completion_date")),
    }


def to_public_summary(row: pd.Series) -> PublicProjectSummary:
    return PublicProjectSummary(**_summary_dict(row))


def to_public_detail(row: pd.Series) -> PublicProjectDetail:
    data = _summary_dict(row)
    description = _clean_text(row.get("work_description"))
    mp_name = _clean_text(row.get("mp"))
    if mp_name:
        mp_name = _NAN_YEARS.sub("", mp_name).strip() or None
    data.update(
        {
            "description": " ".join(description.split()) if description else None,
            "mp_name": mp_name,
            "implementing_agency": _clean_text(row.get("implementing_agency")),
            "recommended_amount": _num(row.get("recommended_amount")),
            "recommended_date": _iso(row.get("recommended_date")),
            "first_expenditure_date": _iso(row.get("first_expenditure_date")),
            "last_expenditure_date": _iso(row.get("last_expenditure_date")),
        }
    )
    return PublicProjectDetail(**data)


# ---------------------------------------------------------------------
# Filtering / search
# ---------------------------------------------------------------------

def _eq(series: pd.Series, value: str) -> pd.Series:
    return series.str.casefold() == str(value).strip().casefold()


def apply_filters(
    frame: pd.DataFrame,
    *,
    state: Optional[str] = None,
    district: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    year: Optional[int] = None,
    detailed: bool = False,
) -> pd.DataFrame:
    result = filter_frame(frame, state=state, district=district)

    if detailed:
        # Only projects that carry a description AND a sanctioned amount.
        has_text = _text_col(result, "work_description").str.strip() != ""
        has_amount = pd.to_numeric(result["sanction_amount"], errors="coerce") > 0
        result = result[has_text & has_amount]

    if year is not None:
        result = result[result["sanction_date"].dt.year == int(year)]

    if category:
        result = result[_eq(result["sector_label"], category)]

    if status:
        result = result[_eq(result["status_label"], status)]

    if search:
        tokens = [t for t in search.lower().split() if t][:MAX_SEARCH_TOKENS]
        for token in tokens:
            result = result[
                result["_haystack"].str.contains(token, regex=False, na=False)
            ]

    return result


def sort_frame(frame: pd.DataFrame, sort: str) -> pd.DataFrame:
    if sort == "sanctioned_desc":
        return frame.sort_values(
            ["sanction_amount", "work_id"], ascending=[False, True], na_position="last"
        )
    if sort == "expenditure_desc":
        return frame.sort_values(
            ["total_expenditure", "work_id"], ascending=[False, True], na_position="last"
        )
    return frame.sort_values(
        ["_recent", "work_id"], ascending=[False, True], na_position="last"
    )


def query_projects(
    *,
    page: int,
    page_size: int,
    sort: str,
    **filters: Optional[str],
) -> PublicProjectResults:
    frame = apply_filters(prepared_frame(), **filters)
    total = int(len(frame))
    total_pages = max(1, math.ceil(total / page_size)) if total else 0

    ordered = sort_frame(frame, sort)
    start = (page - 1) * page_size
    window = ordered.iloc[start : start + page_size]

    return PublicProjectResults(
        items=[to_public_summary(row) for _, row in window.iterrows()],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_project(project_id: str) -> Optional[PublicProjectDetail]:
    frame = prepared_frame()
    match = frame[frame["work_id"] == project_id.strip()]
    if match.empty:
        return None
    return to_public_detail(match.iloc[0])


# ---------------------------------------------------------------------
# Options / meta
# ---------------------------------------------------------------------

def _options(series: pd.Series, *, drop_unspecified: bool = True) -> list[FilterOption]:
    counts = series.value_counts()
    rows = [
        FilterOption(value=str(name), count=int(count))
        for name, count in counts.items()
        if not (drop_unspecified and name == NOT_SPECIFIED)
    ]
    return sorted(rows, key=lambda r: r.value.casefold())


def filter_options(state: Optional[str] = None) -> PublicFilterOptions:
    frame = prepared_frame()
    districts: list[FilterOption] = []
    if state:
        scoped = filter_frame(frame, state=state)
        districts = _options(scoped["district_label"])

    statuses = [
        FilterOption(value=str(name), count=int(count))
        for name, count in frame["status_label"].value_counts().items()
    ]

    year_counts = frame["sanction_date"].dt.year.dropna().astype(int).value_counts()
    years = [
        FilterOption(value=str(year), count=int(count))
        for year, count in sorted(year_counts.items(), reverse=True)
    ]

    return PublicFilterOptions(
        years=years,
        states=_options(frame["state_label"]),
        districts=districts,
        categories=_options(frame["sector_label"]),
        statuses=statuses,
    )


def build_meta(frame: pd.DataFrame) -> PublicMeta:
    refreshed: Optional[str] = None
    try:
        refreshed = datetime.fromtimestamp(
            CANONICAL_PROJECTS_PATH.stat().st_mtime, tz=timezone.utc
        ).isoformat()
    except OSError:
        refreshed = None

    latest: Optional[str] = None
    candidates = []
    for column in (
        "last_expenditure_date",
        "completion_date",
        "sanction_date",
        "recommended_date",
    ):
        if column in frame.columns and frame[column].notna().any():
            candidates.append(frame[column].max())
    if candidates:
        latest = _iso(max(candidates))

    return PublicMeta(
        total_projects=int(len(frame)),
        dataset_refreshed_at=refreshed,
        latest_record_date=latest,
        source_note=SOURCE_NOTE,
    )


# ---------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------

def _area_rows(frame: pd.DataFrame, by: str, name_col: str) -> list[AreaRow]:
    if frame.empty:
        return []

    work = frame.assign(
        _san=pd.to_numeric(frame["sanction_amount"], errors="coerce").fillna(0.0),
        _exp=pd.to_numeric(frame["total_expenditure"], errors="coerce").fillna(0.0),
        _done=(frame["status_label"] == "Completed").astype(int),
        _ongoing=(frame["status_label"] == "Ongoing").astype(int),
    )

    grouped = (
        work.groupby(by, dropna=False)
        .agg(
            project_count=("work_id", "nunique"),
            sanctioned=("_san", "sum"),
            expenditure=("_exp", "sum"),
            completed=("_done", "sum"),
            ongoing=("_ongoing", "sum"),
            state=("state_label", "first"),
        )
        .reset_index()
        .sort_values(["project_count", by], ascending=[False, True])
    )

    rows: list[AreaRow] = []
    for _, row in grouped.iterrows():
        sanctioned = float(row["sanctioned"])
        expenditure = float(row["expenditure"])
        rows.append(
            AreaRow(
                name=str(row[name_col]),
                state=_clean_text(row["state"]),
                project_count=int(row["project_count"]),
                sanctioned_amount=sanctioned,
                expenditure=expenditure,
                completed_projects=int(row["completed"]),
                ongoing_projects=int(row["ongoing"]),
                utilisation_percent=(
                    expenditure / sanctioned * 100 if sanctioned > 0 else None
                ),
            )
        )
    return rows


def area_breakdown(
    *,
    state: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
) -> PublicAreaResponse:
    frame = apply_filters(
        prepared_frame(), state=state, category=category, status=status
    )
    if state:
        return PublicAreaResponse(
            level="district",
            state=state,
            rows=_area_rows(frame, "district_label", "district_label"),
        )
    return PublicAreaResponse(
        level="state",
        state=None,
        rows=_area_rows(frame, "state_label", "state_label"),
    )


def _sector_stats(frame: pd.DataFrame) -> list[SectorStat]:
    if frame.empty:
        return []
    work = frame.assign(
        _san=pd.to_numeric(frame["sanction_amount"], errors="coerce").fillna(0.0),
        _exp=pd.to_numeric(frame["total_expenditure"], errors="coerce").fillna(0.0),
    )
    grouped = (
        work.groupby("sector_label")
        .agg(count=("work_id", "nunique"), san=("_san", "sum"), exp=("_exp", "sum"))
        .reset_index()
        .sort_values("count", ascending=False)
    )
    return [
        SectorStat(
            category=str(row["sector_label"]),
            count=int(row["count"]),
            total_sanctioned_amount=float(row["san"]),
            total_expenditure=float(row["exp"]),
        )
        for _, row in grouped.iterrows()
    ]


def _utilisation_basis(frame: pd.DataFrame) -> UtilisationBasis:
    sanctioned = pd.to_numeric(frame["sanction_amount"], errors="coerce")
    expenditure = pd.to_numeric(frame["total_expenditure"], errors="coerce")
    basis = sanctioned > 0

    san_sum = float(sanctioned[basis].sum()) if basis.any() else 0.0
    exp_sum = float(expenditure[basis].fillna(0).sum()) if basis.any() else 0.0

    return UtilisationBasis(
        percent=(exp_sum / san_sum * 100) if san_sum > 0 else None,
        projects_with_sanctioned_amount=int(basis.sum()),
        sanctioned_amount=san_sum,
        expenditure_on_those_projects=exp_sum,
        projects_with_expenditure_record=int(expenditure.notna().sum()),
        total_projects=int(len(frame)),
    )


def build_summary(
    state: Optional[str] = None, district: Optional[str] = None
) -> Optional[PublicSummary]:
    """Scoped summary. Returns None when the scope has no projects."""
    full = prepared_frame()
    scoped = filter_frame(full, state=state, district=district)

    if (state or district) and scoped.empty:
        return None

    by_state = _area_rows(scoped, "state_label", "state_label")
    by_district = (
        _area_rows(scoped, "district_label", "district_label") if state else []
    )

    return PublicSummary(
        scope_state=state,
        scope_district=district,
        kpis=PublicKpis(**compute_public_kpis(scoped)),
        utilisation=_utilisation_basis(scoped),
        status_distribution=[
            StatusCount(**row) for row in compute_status_distribution(scoped)
        ],
        by_state=by_state,
        by_district=by_district,
        by_category=_sector_stats(scoped),
        meta=build_meta(full),
    )