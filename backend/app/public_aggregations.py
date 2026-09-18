"""
Phase 5: dedicated PUBLIC aggregation layer.

Why this module exists
----------------------
`app/aggregations.py` is the shared (risk-aware) aggregation layer used by
the authenticated Dashboard/Analytics/Reports routes. It knows about
Risk Fusion, risk levels and risk-by-state.

The public Overview must never touch any of that, so Phase 5 gives the
public surface its own, physically separate contract:

    canonical_projects.csv  ->  public_aggregations.py  ->  /public/insights

Nothing in this module imports Risk Fusion, reads
`project_risk_scores.csv`, or references risk_score / risk_level /
anomaly / duplicate / isolation-forest / AI-reasoning / alert /
investigation fields. Separation is structural, not a matter of
remembering to filter fields at serialization time.

Data source
-----------
Every figure below comes from the SAME canonical dataset the ML pipeline
uses -- `data/processed/canonical_projects.csv`, keyed by `work_id` --
so the public `project_id` is the canonical project id, identical to the
one the authenticated views use. State and district aggregates are
therefore derived from the canonical source, not from a second universe.

Honesty rules applied throughout
--------------------------------
*   No monthly/yearly value is ever invented. Trend points are built by
    grouping REAL dates that exist in the canonical dataset
    (`sanction_date`, `completion_date`, `last_expenditure_date`).
*   Months inside an observed range that genuinely have no records are
    emitted with a value of 0 AND `has_records=False`, so the chart axis
    stays continuous without implying that data was recorded.
*   Coverage is reported explicitly (see `compute_data_coverage`) rather
    than hidden -- e.g. only ~20% of canonical projects carry any
    expenditure transaction date at all.
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from app.aggregations import (
    CANONICAL_PROJECTS_PATH,
    load_canonical_projects,
)

# =====================================================================
# Public-safe column allowlist
#
# An allowlist (rather than a denylist of risk columns) means a new
# column appearing in canonical_projects.csv can never leak into a
# public response by default.
# =====================================================================

PUBLIC_COLUMNS: tuple[str, ...] = (
    "work_id",
    "state",
    "district",
    "constituency",
    "work_category",
    "work_description",
    "implementing_agency",
    "mp",
    "status",
    "work_status",
    "sanction_amount",
    "recommended_amount",
    "total_expenditure",
    "recommended_date",
    "sanction_date",
    "completion_date",
    "first_expenditure_date",
    "last_expenditure_date",
)

DATE_COLUMNS: tuple[str, ...] = (
    "recommended_date",
    "sanction_date",
    "completion_date",
    "first_expenditure_date",
    "last_expenditure_date",
)

NUMERIC_COLUMNS: tuple[str, ...] = (
    "sanction_amount",
    "recommended_amount",
    "total_expenditure",
)

NOT_SPECIFIED = "Not specified"

# Canonical `status` values observed in the dataset are upper-snake
# (COMPLETED / ONGOING / SANCTIONED / NOT_SPECIFIED). They are mapped to
# display labels here so the public UI never shows raw enum tokens.
# Anything unmapped is title-cased rather than dropped.
STATUS_LABELS: dict[str, str] = {
    "COMPLETED": "Completed",
    "ONGOING": "Ongoing",
    "SANCTIONED": "Sanctioned",
    "RECOMMENDED": "Recommended",
    "NOT_SPECIFIED": NOT_SPECIFIED,
}

COMPLETED_LABEL = "Completed"

# "Active" = explicitly in the delivery pipeline (sanctioned or ongoing).
# Projects with no recorded status are NOT folded in here -- they are
# reported separately as `status_not_specified`.
ACTIVE_LABELS = ("Sanctioned", "Ongoing")


# =====================================================================
# Frame loading / normalization
# =====================================================================

_FRAME_CACHE: dict[str, Any] = {"key": None, "frame": None}


def _status_label(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return NOT_SPECIFIED

    text = str(value).strip()

    if not text or text.lower() == "nan":
        return NOT_SPECIFIED

    mapped = STATUS_LABELS.get(text.upper())

    if mapped:
        return mapped

    return text.replace("_", " ").title()


def _clean_text_series(frame: pd.DataFrame, column: str) -> pd.Series:
    """Return a stripped string column, with blanks as ``Not specified``."""
    if column not in frame.columns:
        return pd.Series(NOT_SPECIFIED, index=frame.index, dtype="object")

    series = (
        frame[column]
        .astype("object")
        .where(frame[column].notna(), NOT_SPECIFIED)
        .astype(str)
        .str.strip()
    )

    return series.replace({"": NOT_SPECIFIED, "nan": NOT_SPECIFIED, "NaN": NOT_SPECIFIED})


def build_public_frame(canonical_df: pd.DataFrame) -> pd.DataFrame:
    """Project the canonical dataset down to public-safe columns only.

    Applies the allowlist, coerces dates/numerics once, and normalizes
    state/district/category labels so every downstream aggregate groups
    consistently.
    """
    available = [c for c in PUBLIC_COLUMNS if c in canonical_df.columns]

    frame = canonical_df[available].copy()

    frame["work_id"] = frame["work_id"].astype(str).str.strip()

    for column in DATE_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce")
        else:
            frame[column] = pd.NaT

    for column in NUMERIC_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        else:
            frame[column] = pd.NA

    frame["state_label"] = _clean_text_series(frame, "state")
    frame["district_label"] = _clean_text_series(frame, "district")
    frame["category_label"] = _clean_text_series(frame, "work_category")

    if "status" in frame.columns:
        frame["status_label"] = frame["status"].map(_status_label)
    else:
        frame["status_label"] = NOT_SPECIFIED

    frame["is_completed"] = frame["status_label"] == COMPLETED_LABEL
    frame["is_active"] = frame["status_label"].isin(ACTIVE_LABELS)

    return frame


def load_public_frame() -> pd.DataFrame:
    """Load + normalize the canonical dataset, cached on file mtime/size.

    The public Overview is anonymous and therefore the most-hit route in
    the app; re-parsing a 43k-row CSV on every request would be wasteful.
    The cache key is the CSV's (mtime, size), so a re-run of the ML
    pipeline that rewrites canonical_projects.csv is picked up
    automatically without a restart.
    """
    try:
        stat = CANONICAL_PROJECTS_PATH.stat()
        key = (str(CANONICAL_PROJECTS_PATH), stat.st_mtime_ns, stat.st_size)
    except OSError:
        key = None

    if key is not None and _FRAME_CACHE["key"] == key:
        return _FRAME_CACHE["frame"]

    frame = build_public_frame(load_canonical_projects())

    _FRAME_CACHE["key"] = key
    _FRAME_CACHE["frame"] = frame

    return frame


def reset_public_frame_cache() -> None:
    """Drop the cached frame (used by tests)."""
    _FRAME_CACHE["key"] = None
    _FRAME_CACHE["frame"] = None


# =====================================================================
# Small helpers
# =====================================================================

def _sum(series: pd.Series) -> float:
    total = pd.to_numeric(series, errors="coerce").sum()
    return float(total) if pd.notna(total) else 0.0


def _optional_float(value: Any) -> Optional[float]:
    if value is None or pd.isna(value):
        return None
    return float(value)


def filter_frame(
    frame: pd.DataFrame,
    state: Optional[str] = None,
    district: Optional[str] = None,
) -> pd.DataFrame:
    """Case-insensitive state/district narrowing used by the drilldown."""
    result = frame

    if state:
        result = result[
            result["state_label"].str.casefold() == str(state).strip().casefold()
        ]

    if district:
        result = result[
            result["district_label"].str.casefold() == str(district).strip().casefold()
        ]

    return result


# =====================================================================
# Public KPIs
# =====================================================================

def compute_public_kpis(frame: pd.DataFrame) -> dict[str, Any]:
    """Portfolio-level KPIs that are safe for anonymous visitors.

    Deliberately contains no risk/review/investigation counts. Financial
    progress is derived arithmetically from two public figures
    (expenditure / sanctioned amount) rather than from any model output.
    """
    total_projects = int(frame["work_id"].nunique()) if not frame.empty else 0

    sanctioned = pd.to_numeric(frame.get("sanction_amount"), errors="coerce")
    expenditure = pd.to_numeric(frame.get("total_expenditure"), errors="coerce")

    total_sanctioned = _sum(sanctioned)
    total_expenditure = _sum(expenditure)

    completed_projects = int(frame["is_completed"].sum()) if not frame.empty else 0
    active_works = int(frame["is_active"].sum()) if not frame.empty else 0

    status_not_specified = max(
        total_projects - completed_projects - active_works,
        0,
    )

    # Portfolio-level utilisation: total spent against total sanctioned.
    # Reported as None (not 0) when nothing is sanctioned, so "no data"
    # is never rendered as "0% utilised".
    if total_sanctioned > 0:
        expenditure_utilisation = total_expenditure / total_sanctioned * 100
    else:
        expenditure_utilisation = None

    states_covered = int(
        frame.loc[frame["state_label"] != NOT_SPECIFIED, "state_label"].nunique()
    ) if not frame.empty else 0

    districts_covered = int(
        frame.loc[frame["district_label"] != NOT_SPECIFIED, "district_label"].nunique()
    ) if not frame.empty else 0

    completion_rate = (
        completed_projects / total_projects * 100 if total_projects else None
    )

    return {
        "total_projects": total_projects,
        "total_sanctioned_amount": total_sanctioned,
        "total_expenditure": total_expenditure,
        "completed_projects": completed_projects,
        "active_works": active_works,
        "status_not_specified": status_not_specified,
        "expenditure_utilisation_percent": _optional_float(expenditure_utilisation),
        "completion_rate_percent": _optional_float(completion_rate),
        "states_covered": states_covered,
        "districts_covered": districts_covered,
    }


# =====================================================================
# Trends (real dates only)
# =====================================================================

def _monthly_points(
    frame: pd.DataFrame,
    date_column: str,
    value_column: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Group real dates into a continuous monthly series.

    Only months between the FIRST and LAST observed date are emitted.
    Interior months with no source rows are returned with
    ``has_records=False`` and zeroed figures -- that is a statement that
    nothing was recorded, not an invented value. If the column has no
    usable dates at all, an empty list is returned so the caller can show
    an explicit "not available" state instead of a fake chart.
    """
    if frame.empty or date_column not in frame.columns:
        return []

    dated = frame[frame[date_column].notna()]

    if dated.empty:
        return []

    periods = dated[date_column].dt.to_period("M")

    counts = periods.value_counts().sort_index()

    if value_column is not None:
        values = (
            pd.to_numeric(dated[value_column], errors="coerce")
            .groupby(periods)
            .sum()
        )
    else:
        values = None

    full_index = pd.period_range(
        start=counts.index.min(),
        end=counts.index.max(),
        freq="M",
    )

    points: list[dict[str, Any]] = []

    for period in full_index:
        count = int(counts.get(period, 0))

        point: dict[str, Any] = {
            "period": str(period),
            "label": period.strftime("%b %Y"),
            "project_count": count,
            "has_records": count > 0,
        }

        if values is not None:
            raw = values.get(period, 0)
            point["amount"] = float(raw) if pd.notna(raw) else 0.0

        points.append(point)

    return points


def compute_expenditure_trend(frame: pd.DataFrame) -> dict[str, Any]:
    """Real expenditure over time.

    canonical_projects.csv stores `total_expenditure` as a per-project
    LIFETIME total plus the first/last dates of that project's
    expenditure transactions -- it does not store a per-month
    transaction ledger. So a project's total is attributed to the month
    of its MOST RECENT expenditure transaction (`last_expenditure_date`).

    This is stated in `basis` and surfaced in the UI rather than being
    presented as a true monthly cash-flow series, because splitting a
    lifetime total across months would require inventing values.
    """
    points = _monthly_points(
        frame,
        "last_expenditure_date",
        value_column="total_expenditure",
    )

    covered = int(frame["last_expenditure_date"].notna().sum()) if not frame.empty else 0
    total = int(len(frame))

    return {
        "points": points,
        "basis": (
            "Each project's total recorded expenditure is attributed to the "
            "month of its most recent expenditure transaction. The source "
            "dataset does not contain a per-month transaction ledger."
        ),
        "projects_with_data": covered,
        "total_projects": total,
        "coverage_percent": _optional_float(covered / total * 100) if total else None,
    }


def compute_completion_trend(frame: pd.DataFrame) -> dict[str, Any]:
    """Real works-completed over time, grouped on `completion_date`."""
    points = _monthly_points(frame, "completion_date")

    covered = int(frame["completion_date"].notna().sum()) if not frame.empty else 0
    total = int(len(frame))

    return {
        "points": points,
        "basis": (
            "Works counted in the month of their recorded completion date."
        ),
        "projects_with_data": covered,
        "total_projects": total,
        "coverage_percent": _optional_float(covered / total * 100) if total else None,
    }


def compute_sanction_trend(frame: pd.DataFrame) -> dict[str, Any]:
    """Real sanctioned amount over time, grouped on `sanction_date`.

    Included because `sanction_date` + `sanction_amount` are the
    best-covered pair of financial fields in the canonical dataset, so
    this is the most reliable financial time series available publicly.
    """
    points = _monthly_points(
        frame,
        "sanction_date",
        value_column="sanction_amount",
    )

    covered = int(frame["sanction_date"].notna().sum()) if not frame.empty else 0
    total = int(len(frame))

    return {
        "points": points,
        "basis": (
            "Sanctioned amount attributed to the month of the recorded "
            "sanction date."
        ),
        "projects_with_data": covered,
        "total_projects": total,
        "coverage_percent": _optional_float(covered / total * 100) if total else None,
    }


# =====================================================================
# State / district insights
# =====================================================================

def _aggregate(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    work = frame.copy()

    work["_sanction"] = pd.to_numeric(
        work.get("sanction_amount"), errors="coerce"
    ).fillna(0)

    work["_expenditure"] = pd.to_numeric(
        work.get("total_expenditure"), errors="coerce"
    ).fillna(0)

    work["_completed"] = work["is_completed"].astype(int)
    work["_active"] = work["is_active"].astype(int)

    grouped = (
        work.groupby(group_columns, dropna=False)
        .agg(
            project_count=("work_id", "nunique"),
            total_sanctioned_amount=("_sanction", "sum"),
            total_expenditure=("_expenditure", "sum"),
            completed_projects=("_completed", "sum"),
            active_works=("_active", "sum"),
        )
        .reset_index()
    )

    return grouped


def _row_to_public_stat(row: pd.Series) -> dict[str, Any]:
    sanctioned = float(row["total_sanctioned_amount"])
    expenditure = float(row["total_expenditure"])
    project_count = int(row["project_count"])
    completed = int(row["completed_projects"])

    return {
        "project_count": project_count,
        "total_sanctioned_amount": sanctioned,
        "total_expenditure": expenditure,
        "completed_projects": completed,
        "active_works": int(row["active_works"]),
        "expenditure_utilisation_percent": (
            expenditure / sanctioned * 100 if sanctioned > 0 else None
        ),
        "completion_rate_percent": (
            completed / project_count * 100 if project_count else None
        ),
    }


def compute_state_insights(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Per-state public counts + financial aggregates, richest first."""
    if frame.empty:
        return []

    grouped = _aggregate(frame, ["state_label"])

    districts = (
        frame.loc[frame["district_label"] != NOT_SPECIFIED]
        .groupby("state_label")["district_label"]
        .nunique()
    )

    grouped = grouped.sort_values(
        ["total_expenditure", "project_count"],
        ascending=[False, False],
    )

    return [
        {
            "state": str(row["state_label"]),
            "district_count": int(districts.get(row["state_label"], 0)),
            **_row_to_public_stat(row),
        }
        for _, row in grouped.iterrows()
    ]


def compute_district_insights(
    frame: pd.DataFrame,
    state: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Per-district public aggregates, optionally scoped to one state.

    District is carried on every canonical row (resolved by the
    canonical pipeline's `district_source` logic), so this drilldown uses
    the same project universe and the same canonical `work_id` as every
    other public figure. Rows whose district is genuinely unknown are
    kept under "Not specified" rather than dropped, so district counts
    always reconcile with the state total.
    """
    scoped = filter_frame(frame, state=state)

    if scoped.empty:
        return []

    grouped = _aggregate(scoped, ["state_label", "district_label"])

    grouped = grouped.sort_values(
        ["total_expenditure", "project_count"],
        ascending=[False, False],
    )

    return [
        {
            "state": str(row["state_label"]),
            "district": str(row["district_label"]),
            **_row_to_public_stat(row),
        }
        for _, row in grouped.iterrows()
    ]


# =====================================================================
# Categories / status
# =====================================================================

def compute_category_breakdown(
    frame: pd.DataFrame,
    limit: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Project count + financials per work category."""
    if frame.empty:
        return []

    grouped = _aggregate(frame, ["category_label"]).sort_values(
        "project_count",
        ascending=False,
    )

    if limit:
        grouped = grouped.head(limit)

    return [
        {
            "work_type": str(row["category_label"]),
            "count": int(row["project_count"]),
            "total_sanctioned_amount": float(row["total_sanctioned_amount"]),
            "total_expenditure": float(row["total_expenditure"]),
        }
        for _, row in grouped.iterrows()
    ]


def compute_status_distribution(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Lifecycle-status counts using display labels."""
    if frame.empty:
        return []

    counts = frame["status_label"].value_counts().sort_values(ascending=False)

    return [
        {"status": str(name), "count": int(count)}
        for name, count in counts.items()
    ]


# =====================================================================
# Public project summaries
# =====================================================================

def _date_or_none(value: Any):
    if value is None or pd.isna(value):
        return None
    return value.date()


def _text_or_none(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None

    text = str(value).strip()

    if not text or text.lower() == "nan" or text == NOT_SPECIFIED:
        return None

    return text


def to_public_project(row: pd.Series) -> dict[str, Any]:
    """Map one canonical row onto the public project field set.

    Mirrors `PublicProjectOut` exactly. `project_id` is the canonical
    `work_id`, so a public link resolves to the same project the
    authenticated views use.
    """
    sanctioned = pd.to_numeric(row.get("sanction_amount"), errors="coerce")
    expenditure = pd.to_numeric(row.get("total_expenditure"), errors="coerce")

    financial_progress = None

    if pd.notna(sanctioned) and sanctioned > 0 and pd.notna(expenditure):
        financial_progress = float(expenditure / sanctioned * 100)

    return {
        "project_id": str(row.get("work_id")),
        "state": _text_or_none(row.get("state_label")),
        "district": _text_or_none(row.get("district_label")),
        "constituency": _text_or_none(row.get("constituency")),
        "mp_name": _text_or_none(row.get("mp")),
        "work_type": _text_or_none(row.get("category_label")),
        "implementing_agency": _text_or_none(row.get("implementing_agency")),
        "sanctioned_amount": _optional_float(sanctioned),
        "expenditure": _optional_float(expenditure),
        "financial_progress": financial_progress,
        "status": _text_or_none(row.get("status_label")),
        "sanction_date": _date_or_none(row.get("sanction_date")),
        # The canonical dataset has no separate "start date" column;
        # sanction is the first public lifecycle milestone it records.
        "start_date": _date_or_none(row.get("sanction_date")),
        # No expected/target completion date exists in the source data --
        # reported as null rather than estimated.
        "expected_completion": None,
        "actual_completion": _date_or_none(row.get("completion_date")),
    }


def compute_recent_public_projects(
    frame: pd.DataFrame,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Most recently active public projects, ordered by real dates only."""
    if frame.empty or limit <= 0:
        return []

    work = frame.copy()

    work["_recent"] = (
        work["last_expenditure_date"]
        .fillna(work["completion_date"])
        .fillna(work["sanction_date"])
    )

    work = work.sort_values(
        by=["_recent", "work_id"],
        ascending=[False, True],
        na_position="last",
    ).head(limit)

    return [to_public_project(row) for _, row in work.iterrows()]


# =====================================================================
# Data coverage / limitations
# =====================================================================

def compute_data_coverage(frame: pd.DataFrame) -> dict[str, Any]:
    """Report what the source data does and does not support.

    Phase 5 requirement: surface limitations (missing dates, missing
    amounts) explicitly instead of silently zero-filling them.
    """
    total = int(len(frame))

    def _cov(column: str) -> dict[str, Any]:
        present = int(frame[column].notna().sum()) if total else 0
        return {
            "field": column,
            "projects_with_data": present,
            "total_projects": total,
            "coverage_percent": _optional_float(present / total * 100) if total else None,
        }

    fields = [
        _cov("sanction_date"),
        _cov("completion_date"),
        _cov("last_expenditure_date"),
        _cov("sanction_amount"),
        _cov("total_expenditure"),
    ]

    notes: list[str] = [
        "All figures are aggregated from the canonical MPLADS project "
        "dataset and are keyed by the canonical project id (work_id).",
        "Projects with no recorded value for a field are excluded from "
        "that field's aggregate rather than counted as zero.",
        "The source dataset contains no expected/target completion date, "
        "so no delay or overdue figure is published.",
    ]

    expenditure_dates = int(frame["last_expenditure_date"].notna().sum()) if total else 0

    if total and expenditure_dates < total:
        notes.append(
            f"Expenditure transaction dates exist for {expenditure_dates:,} of "
            f"{total:,} projects, so the expenditure trend covers only that "
            "subset of the portfolio."
        )

    completion_dates = int(frame["completion_date"].notna().sum()) if total else 0

    if total and completion_dates < total:
        notes.append(
            f"Completion dates exist for {completion_dates:,} of {total:,} "
            "projects; works completed without a recorded date are not "
            "placed on the completion trend."
        )

    unknown_states = int((frame["state_label"] == NOT_SPECIFIED).sum()) if total else 0

    if unknown_states:
        notes.append(
            f"{unknown_states:,} projects have no recorded state and are "
            "grouped under 'Not specified'."
        )

    unknown_districts = int(
        (frame["district_label"] == NOT_SPECIFIED).sum()
    ) if total else 0

    if unknown_districts:
        notes.append(
            f"{unknown_districts:,} projects have no recorded district and are "
            "grouped under 'Not specified'."
        )

    return {"fields": fields, "notes": notes}
