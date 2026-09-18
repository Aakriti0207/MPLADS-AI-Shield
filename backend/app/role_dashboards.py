"""
Scoped dashboard aggregation for the MP, State Nodal and District
Authority personas.

Everything in this module operates on frames that have ALREADY been
reduced to the caller's authorized scope by app/rbac.py. Nothing here
decides who may see what -- that decision is made once, upstream, and
this module only shapes the authorized records into the figures each
cockpit needs.

Three rules this module keeps to:

1.  Never recompute risk. `risk_score`, `risk_level`, `top_reason_1` and
    `component_breakdown` are read straight from the Risk Fusion output.
    A project scoring 67.4 reads 67.4 for an MP, a District Authority, a
    State Nodal officer and the Ministry alike. Only WHICH projects are
    in the frame differs.

2.  Never fabricate a metric. Where the source has no value -- physical
    progress, for instance, which canonical_projects.csv does not carry
    at all -- the field is None and the UI renders "Data unavailable".
    There is deliberately no composite "district ranking score": no such
    metric exists in the data, and inventing one would present a made-up
    number as a finding.

3.  Never aggregate nationally and hide the rest. Every total below is
    computed over the scoped frame only, which is also why these
    dashboards are cheap: an MP dashboard touches a few hundred rows,
    not 43,863.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import pandas as pd

from app.rbac import (
    ROLE_DISTRICT_AUTHORITY,
    ROLE_MP,
    ROLE_STATE_NODAL,
    UserScope,
)
from app.schemas import (
    CategoryStat,
    DistrictPerformanceRow,
    ScopedKpis,
    ScopedProjectRow,
    StatusCount,
)

# Risk levels that put a project on an attention/priority list. Uses the
# Risk Fusion vocabulary as-is rather than a second threshold of our own.
ATTENTION_LEVELS = {"HIGH", "CRITICAL"}

COMPLETED_STATUSES = {"COMPLETED"}


# =====================================================================
# Small conversion helpers
# =====================================================================

def _num(value: Any) -> Optional[float]:
    numeric = pd.to_numeric(value, errors="coerce")
    if numeric is None or pd.isna(numeric):
        return None
    return float(numeric)


def _dec(value: Any) -> Decimal:
    number = _num(value)
    if number is None:
        return Decimal("0")
    try:
        return Decimal(str(round(number, 2)))
    except (InvalidOperation, ValueError):  # pragma: no cover - defensive
        return Decimal("0")


def _opt_dec(value: Any) -> Optional[Decimal]:
    number = _num(value)
    if number is None:
        return None
    try:
        return Decimal(str(round(number, 2)))
    except (InvalidOperation, ValueError):  # pragma: no cover - defensive
        return None


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def _utilization(sanctioned: Any, expenditure: Any) -> Optional[Decimal]:
    """Expenditure as a percentage of sanctioned amount.

    None -- not 0 -- when there is nothing sanctioned to divide by, so
    "no sanction recorded" is never rendered as "0% utilized".
    """
    total_sanctioned = _num(sanctioned) or 0.0
    total_expenditure = _num(expenditure) or 0.0
    if total_sanctioned <= 0:
        return None
    return Decimal(str(round((total_expenditure / total_sanctioned) * 100, 2)))


def _series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series("", index=df.index, dtype="object")
    return df[column].fillna("").astype(str).str.strip()


def _upper(df: pd.DataFrame, column: str) -> pd.Series:
    return _series(df, column).str.upper()


def _triggered_component(raw: Any) -> Optional[str]:
    """Largest-contributing risk component, read from the Risk Fusion
    `component_breakdown` column. Same field, same rule the Alerts
    detail route already uses -- never a second calculation."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() == "nan":
        return None
    try:
        components = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(components, dict):
        return None

    best_label, best_contribution = None, 0.0
    for name, detail in components.items():
        if not isinstance(detail, dict):
            continue
        contribution = _num(detail.get("contribution")) or 0.0
        if contribution > best_contribution:
            best_contribution = contribution
            best_label = detail.get("label") or name
    return best_label


# =====================================================================
# Merge canonical + Risk Fusion
# =====================================================================

RISK_COLUMNS = [
    "work_id",
    "risk_score",
    "risk_level",
    "top_reason_1",
    "component_breakdown",
]


def merge_scoped(canonical_df: pd.DataFrame, risk_df: pd.DataFrame) -> pd.DataFrame:
    """Join the scoped canonical frame to its Risk Fusion rows.

    A left join: a canonical project with no Risk Fusion row still
    appears (with a null risk), because dropping it would silently
    understate the project counts an officer is accountable for.
    """
    available = [c for c in RISK_COLUMNS if c in risk_df.columns]
    slim_risk = risk_df[available].copy() if available else pd.DataFrame(columns=["work_id"])
    merged = canonical_df.merge(slim_risk, on="work_id", how="left", suffixes=("", "_risk"))
    return merged


# =====================================================================
# KPIs
# =====================================================================

def compute_kpis(merged: pd.DataFrame, scope: UserScope) -> ScopedKpis:
    """Headline figures over the scoped frame."""
    total_projects = int(len(merged))

    status_upper = _upper(merged, "status")
    completed = int(status_upper.isin(COMPLETED_STATUSES).sum())
    active = total_projects - completed

    sanctioned = pd.to_numeric(merged.get("sanction_amount"), errors="coerce").sum() if total_projects else 0
    expenditure = pd.to_numeric(merged.get("total_expenditure"), errors="coerce").sum() if total_projects else 0

    risk_upper = _upper(merged, "risk_level")
    high_risk = int(risk_upper.isin(ATTENTION_LEVELS).sum())

    districts_in_scope = None
    districts_requiring_attention = None
    constituencies_in_scope = None

    if total_projects:
        districts = _series(merged, "district")
        districts = districts[districts != ""]
        districts_in_scope = int(districts.nunique())

        constituencies = _series(merged, "constituency")
        constituencies = constituencies[constituencies != ""]
        constituencies_in_scope = int(constituencies.nunique())

        if scope.role in (ROLE_STATE_NODAL,) or scope.scope_type == "national":
            attention_frame = merged[risk_upper.isin(ATTENTION_LEVELS)]
            attention_districts = _series(attention_frame, "district")
            attention_districts = attention_districts[attention_districts != ""]
            districts_requiring_attention = int(attention_districts.nunique())

    return ScopedKpis(
        total_projects=total_projects,
        active_projects=active,
        completed_projects=completed,
        total_sanctioned=_dec(sanctioned),
        total_expenditure=_dec(expenditure),
        utilization_percent=_utilization(sanctioned, expenditure),
        # "Requiring attention" and "high risk" are the same population
        # here because Risk Fusion's HIGH/CRITICAL tiers are exactly what
        # the review workflow triages on. They are reported as two fields
        # because the three cockpits label them differently, not because
        # two different calculations exist.
        projects_requiring_attention=high_risk,
        high_risk_projects=high_risk,
        districts_requiring_attention=districts_requiring_attention,
        districts_in_scope=districts_in_scope,
        constituencies_in_scope=constituencies_in_scope,
    )


# =====================================================================
# Distributions
# =====================================================================

def compute_status_distribution(merged: pd.DataFrame) -> list[StatusCount]:
    if merged.empty:
        return []
    statuses = _series(merged, "status").replace("", "NOT_SPECIFIED")
    counts = statuses.value_counts()
    return [StatusCount(status=str(name), count=int(count)) for name, count in counts.items()]


def compute_category_distribution(merged: pd.DataFrame, limit: int = 12) -> list[CategoryStat]:
    if merged.empty or "work_category" not in merged.columns:
        return []

    frame = merged.copy()
    frame["_category"] = _series(frame, "work_category").replace("", "Not specified")
    frame["_sanctioned"] = pd.to_numeric(frame.get("sanction_amount"), errors="coerce").fillna(0)
    frame["_expenditure"] = pd.to_numeric(frame.get("total_expenditure"), errors="coerce").fillna(0)

    grouped = (
        frame.groupby("_category", dropna=False)
        .agg(count=("work_id", "size"), sanctioned=("_sanctioned", "sum"), expenditure=("_expenditure", "sum"))
        .reset_index()
        .sort_values("count", ascending=False)
        .head(limit)
    )

    return [
        CategoryStat(
            label=str(row["_category"]),
            count=int(row["count"]),
            sanctioned=_dec(row["sanctioned"]),
            expenditure=_dec(row["expenditure"]),
        )
        for _, row in grouped.iterrows()
    ]


def compute_risk_level_counts(merged: pd.DataFrame) -> dict[str, int]:
    """Risk tier counts straight from Risk Fusion's own `risk_level`."""
    if merged.empty or "risk_level" not in merged.columns:
        return {}
    levels = _upper(merged, "risk_level")
    levels = levels[levels != ""]
    return {str(name): int(count) for name, count in levels.value_counts().items()}


# =====================================================================
# District comparison (State Nodal)
# =====================================================================

def compute_district_performance(merged: pd.DataFrame) -> list[DistrictPerformanceRow]:
    """Per-district aggregates for the State Nodal comparison table.

    Only real metrics: counts, money, utilization and the mean of the
    Risk Fusion scores actually present. `average_risk` is None when no
    project in that district carries a score, so the UI can say "Data
    unavailable" rather than print a misleading 0.
    """
    if merged.empty:
        return []

    frame = merged.copy()
    frame["_district"] = _series(frame, "district").replace("", "Not specified")
    frame["_sanctioned"] = pd.to_numeric(frame.get("sanction_amount"), errors="coerce").fillna(0)
    frame["_expenditure"] = pd.to_numeric(frame.get("total_expenditure"), errors="coerce").fillna(0)
    frame["_completed"] = _upper(frame, "status").isin(COMPLETED_STATUSES)
    frame["_high_risk"] = _upper(frame, "risk_level").isin(ATTENTION_LEVELS)
    frame["_risk_score"] = pd.to_numeric(frame.get("risk_score"), errors="coerce")

    rows: list[DistrictPerformanceRow] = []

    for district, group in frame.groupby("_district", dropna=False):
        sanctioned = float(group["_sanctioned"].sum())
        expenditure = float(group["_expenditure"].sum())
        completed = int(group["_completed"].sum())
        projects = int(len(group))
        scored = group["_risk_score"].dropna()

        rows.append(
            DistrictPerformanceRow(
                district=str(district),
                projects=projects,
                sanctioned=_dec(sanctioned),
                expenditure=_dec(expenditure),
                utilization_percent=_utilization(sanctioned, expenditure),
                completed=completed,
                ongoing=projects - completed,
                high_risk=int(group["_high_risk"].sum()),
                average_risk=_opt_dec(scored.mean()) if len(scored) else None,
            )
        )

    # Highest-exposure districts first, by the count of genuinely
    # high-risk projects -- an actual metric, not a synthetic rank.
    rows.sort(key=lambda r: (-r.high_risk, -r.projects, r.district))
    return rows


# =====================================================================
# Project rows
# =====================================================================

def _to_row(row: pd.Series) -> ScopedProjectRow:
    sanctioned = _opt_dec(row.get("sanction_amount"))
    expenditure = _opt_dec(row.get("total_expenditure"))

    return ScopedProjectRow(
        # The canonical work_id, unchanged. This is the SAME identifier
        # the Project Details page, Risk Fusion, Alerts and Reports use,
        # for every role -- there is no role-specific project id.
        project_id=str(row.get("work_id")).strip(),
        work_description=_text(row.get("work_description")),
        state=_text(row.get("state")),
        district=_text(row.get("district")),
        constituency=_text(row.get("constituency")),
        mp_name=_text(row.get("mp")),
        work_category=_text(row.get("work_category")),
        status=_text(row.get("status")),
        sanctioned_amount=sanctioned,
        expenditure=expenditure,
        utilization_percent=_utilization(row.get("sanction_amount"), row.get("total_expenditure")),
        risk_score=_num(row.get("risk_score")),
        risk_level=_text(row.get("risk_level")),
        top_risk_signal=_text(row.get("top_reason_1")),
        triggered_component=_triggered_component(row.get("component_breakdown")),
        last_updated=None,
    )


def compute_project_rows(merged: pd.DataFrame, limit: int = 50) -> list[ScopedProjectRow]:
    """A stable, highest-risk-first page of the scoped projects."""
    if merged.empty:
        return []
    frame = merged.copy()
    frame["_risk_score"] = pd.to_numeric(frame.get("risk_score"), errors="coerce")
    frame = frame.sort_values(by=["_risk_score", "work_id"], ascending=[False, True], na_position="last")
    return [_to_row(row) for _, row in frame.head(limit).iterrows()]


def compute_attention_projects(merged: pd.DataFrame, limit: int = 20) -> list[ScopedProjectRow]:
    """The review/priority queue: HIGH and CRITICAL projects only,
    ordered by the Risk Fusion score itself."""
    if merged.empty or "risk_level" not in merged.columns:
        return []
    frame = merged[_upper(merged, "risk_level").isin(ATTENTION_LEVELS)].copy()
    if frame.empty:
        return []
    frame["_risk_score"] = pd.to_numeric(frame.get("risk_score"), errors="coerce")
    frame = frame.sort_values(by=["_risk_score", "work_id"], ascending=[False, True], na_position="last")
    return [_to_row(row) for _, row in frame.head(limit).iterrows()]


# =====================================================================
# Data honesty notes
# =====================================================================

def data_notes(merged: pd.DataFrame, scope: UserScope) -> list[str]:
    """Plain statements about what the source data does and does not
    support for this scope, so a gap is never mistaken for a zero."""
    notes: list[str] = []

    if merged.empty:
        notes.append(scope.empty_state_message)
        return notes

    notes.append(
        "Physical progress is not present in the canonical source dataset, "
        "so physical-progress columns show 'Data unavailable' rather than an estimate."
    )

    if "risk_level" in merged.columns:
        unscored = int(_series(merged, "risk_level").eq("").sum())
        if unscored:
            notes.append(
                f"{unscored} of {len(merged)} projects in scope have no Risk Fusion "
                "score in the current run; they are counted in the project totals "
                "but excluded from risk averages."
            )

    if scope.role == ROLE_MP:
        notes.append(
            "Risk signals are advisory prioritisation output for authorised review. "
            "They are not a finding of wrongdoing."
        )

    if scope.role == ROLE_DISTRICT_AUTHORITY:
        notes.append(
            "The priority queue is ordered by the same Risk Fusion score shown "
            "everywhere else in the platform; no district-specific scoring is applied."
        )

    return notes