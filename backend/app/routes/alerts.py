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

from app.auth import get_current_user
from app.database import get_db
from app.models import Project


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
    """Load and cache the production Risk Fusion artifact.

    The cache avoids rereading the large CSV for every Alerts request.
    Restart/reload the backend after regenerating project_risk_scores.csv.
    """

    if not RISK_OUTPUT_PATH.exists():
        raise RuntimeError(
            f"Risk Fusion output not found: {RISK_OUTPUT_PATH}. "
            "Run the Risk Fusion pipeline first."
        )

    df = pd.read_csv(RISK_OUTPUT_PATH, low_memory=False)

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

    df["work_id"] = df["work_id"].astype(str).str.strip()
    df["risk_level"] = (
        df["risk_level"]
        .fillna("LOW")
        .astype(str)
        .str.upper()
        .str.strip()
    )

    # Only valid project IDs are usable as alert records.
    df = df[
        (df["work_id"] != "")
        & (df["work_id"].str.lower() != "nan")
    ].copy()

    # One authoritative Risk Fusion row per project.
    df = df.drop_duplicates(subset=["work_id"], keep="first")

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


# ---------------------------------------------------------------------
# GET /alerts
# ---------------------------------------------------------------------

@router.get("", response_model=list[AlertListItem])
def list_alerts(
    severity: Optional[str] = Query(
        default=None,
        description="Optional filter: critical, high, medium, or low.",
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return compact, one-per-project alert cards.

    The list intentionally contains no explanation text. Open a project and
    call GET /alerts/{project_id} for its reasons and contributing signals.
    """

    risk_df = _load_risk_fusion()

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
    locations = _project_location_map(db, project_ids)

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
):
    """Return the reason and contributing signals for one project.

    ``:path`` is intentional because real MPLADS IDs contain '/'.
    """

    project_id = unquote(project_id).strip()
    if not project_id:
        raise HTTPException(status_code=404, detail="Alert not found")

    risk_df = _load_risk_fusion()
    matches = risk_df[risk_df["work_id"] == project_id]

    if matches.empty:
        raise HTTPException(status_code=404, detail="Alert not found")

    row = matches.iloc[0]
    project = _project_metadata(db, project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

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