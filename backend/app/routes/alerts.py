"""Alert routes for MPLADS AI Shield.

Design
------
* One alert record represents one project, not every individual signal.
* The project's Risk Fusion ``risk_level`` is the ONLY source of alert severity.
* The list endpoint exposes only project identity, location and severity.
* Clicking a project can call GET /alerts/{project_id} to retrieve the
  detailed reasons/signals behind that project's alert.
* HIGH/MEDIUM/LOW/CRITICAL are supported. With the current Risk Fusion
  output, CRITICAL may legitimately be zero.
* Risk Fusion CSV is cached in-process so every request does not reread the
  large CSV from disk.

Alerts are advisory review-priority signals, not confirmations of fraud.

RBAC
----
Alerts are scope-filtered SERVER-SIDE, before the page is cut:

    MP       -> constituency alerts only
    District -> district alerts only
    State    -> state alerts only
    Ministry -> all alerts

Pagination therefore operates on the authorized set, so an out-of-scope
alert can never appear even transiently, and `skip`/`limit` cannot be
walked to reach one. The detail route re-checks scope in its own right:
it is not reachable by guessing a project ID.
"""

import ast
import json
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.aggregations import load_canonical_projects, load_risk_fusion as _load_shared_risk_fusion
from app.auth import get_current_user
from app.database import get_db
from app.models import Project
from app.rbac import (
    UserScope,
    authorized_work_ids,
    get_scope,
    is_row_in_scope,
    narrow_within_scope,
    project_not_found,
)


router = APIRouter(
    prefix="/alerts",
    tags=["alerts"],
    dependencies=[Depends(get_current_user)],
)


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).resolve().parents[2]
RISK_OUTPUT_PATH = BACKEND_ROOT / "data" / "processed" / "project_risk_scores.csv"


# ---------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------

class AlertListItem(BaseModel):
    """Compact alert card shown in the Alerts list."""

    model_config = ConfigDict(from_attributes=True)

    alert_id: str
    project_id: str
    severity: str
    state: Optional[str] = None
    district: Optional[str] = None
    constituency: Optional[str] = None

    # Cheap additions (already in the cached in-process Risk Fusion frame --
    # no extra I/O per row) so the list card can show a risk score and which
    # component triggered it without a second request per project.
    risk_score: Optional[float] = None
    triggered_component: Optional[str] = None
    top_reason: Optional[str] = None


class AlertDetail(BaseModel):
    """Full alert information returned after a project is opened."""

    alert_id: str
    project_id: str
    severity: str
    state: Optional[str] = None
    district: Optional[str] = None
    constituency: Optional[str] = None
    mp_name: Optional[str] = None
    risk_score: Optional[float] = None
    evidence_status: Optional[str] = None
    reasons: list[str]
    signals: list[dict[str, Any]]
    created_at: datetime

    # --- PART 12 additions: Alert Type / Triggered Component / Evidence --
    # alert_type / triggered_component both name the single largest
    # contributing Risk Fusion component for this project (e.g. "Financial
    # Anomaly"), so the Alerts UI can label the card without guessing.
    alert_type: Optional[str] = None
    triggered_component: Optional[str] = None
    evidence: list[dict[str, Any]] = []
    data_quality_notes: list[str] = []


# ---------------------------------------------------------------------
# Risk Fusion configuration
# ---------------------------------------------------------------------

CONTRIBUTION_FIELDS = [
    ("compliance_contribution", "Compliance"),
    ("financial_anomaly_contribution", "Financial anomaly"),
    ("timeline_anomaly_contribution", "Timeline anomaly"),
    ("duplicate_contribution", "Duplicate similarity"),
    ("data_quality_contribution", "Data quality"),
    ("payment_contribution", "Payment pattern"),
    ("isolation_forest_contribution", "Isolation Forest"),
]

SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

# Backwards-compatible export used by app.routes.demo.
SEVERITY_PRIORITY = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


# ---------------------------------------------------------------------
# Cached Risk Fusion loader
# ---------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_risk_fusion() -> pd.DataFrame:
    """Return the current Risk Fusion output, shaped for Alerts.

    This used to independently `pd.read_csv()` project_risk_scores.csv
    on its own -- a second full parse of the same large, JSON-column-
    heavy CSV that app/aggregations.py already loads, caches, and
    accelerates with a Parquet cache (see that module's
    `_read_processed_table`). That meant every Alerts request after a
    cold start paid its own separate, unaccelerated parse, on top of a
    second full copy of the data sitting in memory -- and since
    warm_up_projects() (app/routes/projects.py) only primes the SHARED
    aggregations.py cache, this local cache never benefited from the
    startup warm-up: the first Alerts request after every restart was
    still slow.

    Reusing the shared loader here means this frame comes pre-warmed at
    server startup, same as Dashboard/Projects, and this function now
    only does the Alerts-specific column check + reshaping on top of an
    already-loaded, already-cached DataFrame.
    """

    df = _load_shared_risk_fusion()

    required = {
        "work_id",
        "risk_score",
        "risk_level",
        "evidence_status",
        "risk_reasons",
        "top_reason_1",
        "top_reason_2",
        "top_reason_3",
        "high_severity_signal_count",
    }

    # Domain contribution columns are required for the detail view.
    required.update(column for column, _ in CONTRIBUTION_FIELDS)

    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(
            "Risk Fusion output is missing required columns: "
            + ", ".join(sorted(missing))
        )

    # The shared loader already strips/dedupes work_id and drops
    # blank/nan IDs (see app/aggregations.py's load_risk_fusion). Only
    # the Alerts-specific risk_level normalization is still needed here.
    df = df.copy()
    df["risk_level"] = (
        df["risk_level"]
        .fillna("LOW")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    return df


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _decimal(value: Any) -> Decimal:
    if value is None or pd.isna(value):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _optional_text(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return text


def _severity(value: Any) -> str:
    level = str(value or "LOW").upper().strip()
    return level if level in SEVERITIES else "LOW"


def _risk_score(value: Any) -> Optional[float]:
    number = _decimal(value)
    return float(number) if number else None


def _build_reasons(row: pd.Series) -> list[str]:
    """Return human-readable reasons generated by Risk Fusion.

    ``risk_reasons`` is stored as a JSON-encoded list of individual reason
    sentences (see ml/risk.py's generate_reasons()) -- this parses it into
    separate list items rather than treating the whole serialized JSON
    string as a single (unreadable) reason.
    """

    reasons: list[str] = []

    raw = row.get("risk_reasons")
    if pd.notna(raw):
        text = str(raw).strip()
        if text and text.lower() not in {"nan", "none", "[]", "null"}:
            parsed: Any = None
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError, json.JSONDecodeError):
                try:
                    parsed = ast.literal_eval(text)
                except Exception:
                    parsed = None
            if isinstance(parsed, list):
                reasons.extend(str(item).strip() for item in parsed if str(item).strip())
            elif text not in {"[]"}:
                # Not a recognizable list -- keep the raw text rather than
                # silently dropping a real Risk Fusion explanation.
                reasons.append(text)

    if not reasons:
        for field in ("top_reason_1", "top_reason_2", "top_reason_3"):
            value = row.get(field)
            text = _optional_text(value)
            if text:
                reasons.append(text)

    if not reasons:
        level = _severity(row.get("risk_level"))
        if level == "LOW":
            reasons.append("No elevated Risk Fusion signal was identified for this project.")
        else:
            reasons.append(
                f"Risk Fusion assigned this project {level} risk based on the available evidence."
            )

    return reasons



def _generate_alerts_for_row(
    row: pd.Series,
    generated_at: datetime,
) -> list[dict[str, Any]]:
    """
    Backwards-compatible adapter used by ``app.routes.demo``.

    The old demo code expects this helper to return alert dictionaries, but
    the Alerts architecture is now one alert per project.  Therefore this
    adapter deliberately returns exactly one project-level alert instead of
    recreating the old multi-alert-per-signal behaviour.
    """
    project_id = str(row.get("work_id", "")).strip()
    severity = _severity(row.get("risk_level")).lower()
    score = _risk_score(row.get("risk_score")) or 0.0
    evidence = _optional_text(row.get("evidence_status"))
    reasons = _build_reasons(row)
    triggered_component, _component_evidence = _triggered_component(row)

    message = (
        f"Project {project_id} is currently rated {severity.upper()} "
        f"by the Risk Fusion engine."
    )
    if score is not None:
        message += f" Risk score: {score:.2f}."
    if evidence:
        message += f" Evidence status: {evidence}."
    if reasons:
        message += " " + " ".join(reasons[:3])

    return [
        {
            "alert_id": f"{project_id}:risk",
            "project_id": project_id,
            "alert_type": triggered_component or "project_risk",
            "severity": severity,
            "message": message,
            "sort_score": score,
            "created_at": generated_at,
            "risk_score": score,
            "triggered_component": triggered_component,
            "top_reason": reasons[0] if reasons else None,
        }
    ]

def _build_signals(row: pd.Series) -> list[dict[str, Any]]:
    """Return only domains that contributed to the project's score."""

    signals: list[dict[str, Any]] = []

    for column, label in CONTRIBUTION_FIELDS:
        contribution = _decimal(row.get(column))
        if contribution <= 0:
            continue

        signals.append(
            {
                "type": label,
                "contribution": float(contribution),
            }
        )

    return sorted(
        signals,
        key=lambda item: item["contribution"],
        reverse=True,
    )


def _parse_json_dict(raw: Any) -> dict[str, Any]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return {}
    text = str(raw).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    return {}


def _parse_json_list(raw: Any) -> list[str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except Exception:
        pass
    return []


def _triggered_component(row: pd.Series) -> tuple[Optional[str], list[dict[str, Any]]]:
    """Return (label, evidence) for the single largest contributing component.

    "Triggered Component" and its evidence for the Alerts detail page
    (PART 12) -- sourced directly from ml/risk.py's component_breakdown
    column, never recomputed here.
    """

    components = _parse_json_dict(row.get("component_breakdown"))
    if not components:
        return None, []

    best_name, best_detail = None, None
    best_contribution = 0.0
    for name, detail in components.items():
        if not isinstance(detail, dict):
            continue
        contribution = float(detail.get("contribution") or 0)
        if contribution > best_contribution:
            best_contribution = contribution
            best_name, best_detail = name, detail

    if best_detail is None:
        return None, []

    label = best_detail.get("label") or best_name
    evidence = best_detail.get("evidence") or []
    return label, [e for e in evidence if isinstance(e, dict)]


def _project_location_map(
    db: Session,
    project_ids: list[str],
) -> dict[str, dict[str, Optional[str]]]:
    """Fetch location/jurisdiction only for projects on the current page."""

    if not project_ids:
        return {}

    rows = (
        db.query(
            Project.project_id,
            Project.state,
            Project.district,
            Project.constituency,
        )
        .filter(Project.project_id.in_(project_ids))
        .all()
    )

    return {
        str(row.project_id): {
            "state": _optional_text(row.state),
            "district": _optional_text(row.district),
            "constituency": _optional_text(row.constituency),
        }
        for row in rows
    }


def _project_metadata(db: Session, project_id: str) -> Optional[Project]:
    return (
        db.query(Project)
        .filter(Project.project_id == project_id)
        .first()
    )


@lru_cache(maxsize=1)
def _canonical_location_frame() -> pd.DataFrame:
    """work_id -> state/district/constituency/mp, from the canonical
    dataset.

    The `projects` DB table is incomplete (it has no district value for
    Phase-2-imported rows at all), so using it as the jurisdiction source
    for scoping would silently drop records an officer is entitled to.
    The canonical dataset is the same universe the project and risk APIs
    already treat as authoritative, so alerts scope against that.
    """

    df = load_canonical_projects()
    columns = [c for c in ("work_id", "state", "district", "constituency", "mp") if c in df.columns]
    slim = df[columns].copy()
    slim["work_id"] = slim["work_id"].astype(str).str.strip()
    return slim.set_index("work_id", drop=False)


def _canonical_location_map(project_ids: list[str]) -> dict[str, dict[str, Optional[str]]]:
    """Location lookup for the current page, from the canonical frame."""

    if not project_ids:
        return {}

    frame = _canonical_location_frame()
    present = [pid for pid in project_ids if pid in frame.index]
    if not present:
        return {}

    subset = frame.loc[present]
    return {
        str(row["work_id"]): {
            "state": _optional_text(row.get("state")),
            "district": _optional_text(row.get("district")),
            "constituency": _optional_text(row.get("constituency")),
            "mp": _optional_text(row.get("mp")),
        }
        for _, row in subset.iterrows()
    }


# ---------------------------------------------------------------------
# GET /alerts
# ---------------------------------------------------------------------

@router.get("", response_model=list[AlertListItem])
def list_alerts(
    severity: Optional[str] = Query(
        default=None,
        description="Optional filter: critical, high, medium, or low.",
    ),
    district: Optional[str] = Query(
        default=None,
        description="Optional district filter (must be inside your authorized scope).",
    ),
    constituency: Optional[str] = Query(
        default=None,
        description="Optional constituency filter (must be inside your authorized scope).",
    ),
    state: Optional[str] = Query(
        default=None,
        description="Optional state filter (must be inside your authorized scope).",
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    scope: UserScope = Depends(get_scope),
):
    """Return compact, one-per-project alert cards for the caller's scope.

    The list intentionally contains no explanation text. Open a project and
    call GET /alerts/{project_id} for its reasons and contributing signals.

    Scoping happens before sorting and pagination, so every page is a page
    OF THE AUTHORIZED SET. The optional state/district/constituency filters
    can only narrow inside that set; naming another jurisdiction is a 403.
    """

    risk_df = _load_risk_fusion()

    # -----------------------------------------------------------------
    # RBAC: restrict the alert universe to the caller's authorized
    # projects before anything else happens.
    # -----------------------------------------------------------------

    canonical_df = load_canonical_projects()

    state, district, constituency = narrow_within_scope(
        scope,
        requested_state=state,
        requested_district=district,
        requested_constituency=constituency,
    )

    if not scope.is_national:
        allowed_ids = authorized_work_ids(canonical_df, scope)
        risk_df = risk_df[risk_df["work_id"].isin(allowed_ids)]

    # Optional narrowing filters, applied against the canonical
    # jurisdiction values rather than anything the client asserted.
    location_filters = [
        ("state", state),
        ("district", district),
        ("constituency", constituency),
    ]
    if any(value for _, value in location_filters):
        frame = canonical_df
        for column, value in location_filters:
            if not value or column not in frame.columns:
                continue
            frame = frame[
                frame[column].fillna("").astype(str).str.strip().str.casefold()
                == value.strip().casefold()
            ]
        narrowed_ids = set(frame["work_id"].astype(str).str.strip())
        risk_df = risk_df[risk_df["work_id"].isin(narrowed_ids)]

    requested = None
    if severity is not None:
        requested = severity.upper().strip()
        if requested not in SEVERITIES:
            raise HTTPException(
                status_code=422,
                detail="severity must be one of: critical, high, medium, low",
            )

    work = risk_df.copy()
    work["_severity"] = work["risk_level"].map(_severity)

    if requested:
        work = work[work["_severity"] == requested]

    # Highest-risk projects first, then highest score, then stable project ID.
    work["_severity_order"] = work["_severity"].map(SEVERITY_ORDER)
    work = work.sort_values(
        by=["_severity_order", "risk_score", "work_id"],
        ascending=[True, False, True],
        na_position="last",
    )

    page = work.iloc[skip : skip + limit]
    project_ids = page["work_id"].tolist()
    # Canonical first (complete jurisdiction data), DB row as a fallback
    # for anything the canonical dataset does not carry.
    locations = _project_location_map(db, project_ids)
    canonical_locations = _canonical_location_map(project_ids)
    for pid, values in canonical_locations.items():
        merged_location = dict(locations.get(pid) or {})
        merged_location.update({k: v for k, v in values.items() if v})
        locations[pid] = merged_location

    generated_at = datetime.now(timezone.utc)
    result: list[AlertListItem] = []

    for _, row in page.iterrows():
        project_id = str(row["work_id"])
        location = locations.get(project_id, {})
        triggered_component, _ = _triggered_component(row)
        result.append(
            AlertListItem(
                alert_id=f"{project_id}:risk",
                project_id=project_id,
                severity=_severity(row["risk_level"]).lower(),
                state=location.get("state"),
                district=location.get("district"),
                constituency=location.get("constituency"),
                risk_score=_risk_score(row.get("risk_score")),
                triggered_component=triggered_component,
                top_reason=_optional_text(row.get("top_reason_1")),
            )
        )

    return result


# ---------------------------------------------------------------------
# GET /alerts/{project_id}
# ---------------------------------------------------------------------

@router.get("/{project_id:path}", response_model=AlertDetail)
def get_alert_detail(
    project_id: str,
    db: Session = Depends(get_db),
    scope: UserScope = Depends(get_scope),
):
    """Return the reason and contributing signals for one project.

    ``:path`` is intentional because real MPLADS IDs contain '/'.

    RBAC: authorization is enforced here independently of the list route.
    An alert for a project outside the caller's jurisdiction returns the
    same 404 as an alert that does not exist, so this route cannot be
    used to confirm which work IDs are real.
    """

    project_id = unquote(project_id).strip()
    if not project_id:
        raise project_not_found()

    risk_df = _load_risk_fusion()
    matches = risk_df[risk_df["work_id"] == project_id]

    if matches.empty:
        raise project_not_found()

    row = matches.iloc[0]

    # -----------------------------------------------------------------
    # Scope check against the canonical jurisdiction record.
    # -----------------------------------------------------------------

    canonical_frame = _canonical_location_frame()
    canonical_row = (
        canonical_frame.loc[project_id]
        if project_id in canonical_frame.index
        else None
    )

    if canonical_row is None or not is_row_in_scope(canonical_row, scope):
        raise project_not_found()

    project = _project_metadata(db, project_id)

    # The canonical dataset -- not the incomplete `projects` table -- is
    # the project universe, so a missing DB row is not a 404 here. It
    # only means the location fields fall back to the canonical values.
    class _CanonicalProject:
        state = _optional_text(canonical_row.get("state"))
        district = _optional_text(canonical_row.get("district"))
        constituency = _optional_text(canonical_row.get("constituency"))
        mp_name = _optional_text(canonical_row.get("mp"))

    if project is None:
        project = _CanonicalProject()

    triggered_component, component_evidence = _triggered_component(row)

    return AlertDetail(
        alert_id=f"{project_id}:risk",
        project_id=project_id,
        severity=_severity(row["risk_level"]).lower(),
        state=_optional_text(project.state),
        district=_optional_text(project.district),
        constituency=_optional_text(project.constituency),
        mp_name=_optional_text(project.mp_name),
        risk_score=_risk_score(row["risk_score"]),
        evidence_status=_optional_text(row.get("evidence_status")),
        reasons=_build_reasons(row),
        signals=_build_signals(row),
        created_at=datetime.now(timezone.utc),
        alert_type=triggered_component,
        triggered_component=triggered_component,
        evidence=component_evidence,
        data_quality_notes=_parse_json_list(row.get("data_quality_notes")),
    )