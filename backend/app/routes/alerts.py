"""
Routes for alerts.

Phase 3D update: alerts are no longer hardcoded. There is still no
dedicated `alerts` table (that remains deferred, per app/models.py's
docstring) -- instead, GET /alerts derives alerts on the fly from the
real Phase 2 risk signals already present on `Project` rows, the same
way app/routes/dashboard.py derives its stats live rather than from a
cached/stored table.

Every alert generated here traces back to a genuine, non-NULL Phase 2
column: risk_level, risk_reason_1/2/3, raw_max_similarity +
most_similar_work_id, or one of the six risk component scores. Nothing
about estimated_cost, physical_progress, expected_completion, or
latitude/longitude is used, since those are not populated for real
Phase 2 rows (see app/models.py). Anomaly does not mean fraud -- these
are advisory, review-priority signals only.

Because a single project can legitimately trigger more than one rule
(e.g. HIGH risk_level AND a strong duplicate signal), the candidate set
is built in Python from a single bounded SQL query (only projects that
match at least one trigger condition -- never all 56,323 rows), then
sorted deterministically and paginated in memory. skip/limit still
protect the response size the same way they do on GET /projects.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth import get_current_user
from app.models import Project
from app.schemas import AlertOut

router = APIRouter(
    prefix="/alerts",
    tags=["alerts"],
    dependencies=[Depends(get_current_user)],
)

# --- Thresholds -------------------------------------------------------
# Rule B: only a strong text/feature similarity match counts as a
# possible-duplicate signal. raw_max_similarity is a 0-1 fraction.
DUPLICATE_SIMILARITY_THRESHOLD = Decimal("0.85")
DUPLICATE_HIGH_SEVERITY_THRESHOLD = Decimal("0.95")

# Rule C: a component score >= 80 lines up with the CRITICAL band of the
# same 0-100 classification used for the overall risk_score
# (0-39 LOW / 40-59 MEDIUM / 60-79 HIGH / 80-100 CRITICAL), so alerts
# generated from this rule are labeled "critical".
COMPONENT_ALERT_THRESHOLD = Decimal("80")

# Column -> (alert_type, human label) for Rule C. duplicate_risk_score is
# intentionally excluded here -- duplicate signals are handled by Rule B
# via raw_max_similarity/most_similar_work_id instead.
COMPONENT_FIELDS = [
    ("financial_risk_score", "financial_risk", "Financial risk"),
    ("payment_risk_score", "payment_risk", "Payment risk"),
    ("execution_risk_score", "execution_risk", "Execution risk"),
    ("peer_anomaly_score", "peer_anomaly", "Peer anomaly"),
    ("isolation_forest_score", "anomaly_detection", "Anomaly detection"),
    ("anomaly_risk_score", "anomaly_risk", "Anomaly risk"),
]

SEVERITY_PRIORITY = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _build_candidate_filter():
    """SQL-level filter: only fetch projects that could trigger at least
    one rule, instead of pulling the whole table into Python."""
    component_conditions = [
        getattr(Project, col) >= COMPONENT_ALERT_THRESHOLD
        for col, _, _ in COMPONENT_FIELDS
    ]
    return or_(
        Project.risk_level.in_(["HIGH", "CRITICAL"]),
        (Project.raw_max_similarity >= DUPLICATE_SIMILARITY_THRESHOLD)
        & Project.most_similar_work_id.isnot(None),
        *component_conditions,
    )


def _generate_alerts_for_project(p: Project, generated_at: datetime) -> List[dict]:
    """Return zero or more raw alert dicts for one project row. Every
    field used here is read directly off the row; NULLs are skipped,
    never coerced to 0 or treated as a match."""
    alerts: List[dict] = []
    # Carry the project's own risk_score along for sorting purposes only
    # (not every alert type is itself "about" risk_score, but sorting the
    # whole list by the project's overall priority is still meaningful).
    sort_score = p.risk_score if p.risk_score is not None else Decimal("0")

    # --- Rule A: HIGH / CRITICAL overall risk level ---
    if p.risk_level and p.risk_level.upper() in ("HIGH", "CRITICAL"):
        reasons = [r for r in (p.risk_reason_1, p.risk_reason_2, p.risk_reason_3) if r]
        score_text = f"{p.risk_score}" if p.risk_score is not None else "not available"
        message = (
            f"This project has been assigned {p.risk_level.upper()} risk, "
            f"with a risk score of {score_text}."
        )
        if reasons:
            message += " " + " ".join(reasons)
        alerts.append({
            "alert_id": f"{p.project_id}:high_risk_project",
            "project_id": p.project_id,
            "alert_type": "high_risk_project",
            "severity": p.risk_level.lower(),
            "message": message,
            "sort_score": sort_score,
        })

    # --- Rule B: strong duplicate/similarity signal ---
    if (
        p.raw_max_similarity is not None
        and p.raw_max_similarity >= DUPLICATE_SIMILARITY_THRESHOLD
        and p.most_similar_work_id
    ):
        severity = "high" if p.raw_max_similarity >= DUPLICATE_HIGH_SEVERITY_THRESHOLD else "medium"
        message = (
            f"This project shows a strong similarity signal (similarity score "
            f"{p.raw_max_similarity}) to project {p.most_similar_work_id}. "
            "This is a similarity signal requiring human verification, not a confirmed duplicate."
        )
        alerts.append({
            "alert_id": f"{p.project_id}:possible_duplicate",
            "project_id": p.project_id,
            "alert_type": "possible_duplicate",
            "severity": severity,
            "message": message,
            "sort_score": sort_score,
        })

    # --- Rule C: strong individual risk component ---
    for col, alert_type, label in COMPONENT_FIELDS:
        value: Optional[Decimal] = getattr(p, col)
        if value is not None and value >= COMPONENT_ALERT_THRESHOLD:
            message = (
                f"{label} component scored {value}, indicating a strong "
                "signal in this area that may warrant closer review."
            )
            alerts.append({
                "alert_id": f"{p.project_id}:{alert_type}",
                "project_id": p.project_id,
                "alert_type": alert_type,
                "severity": "critical",
                "message": message,
                "sort_score": sort_score,
            })

    return alerts


@router.get("", response_model=List[AlertOut])
def list_alerts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Derive alerts live from real Phase 2 risk signals on the Project
    table (risk_level, risk_reason_1/2/3, raw_max_similarity +
    most_similar_work_id, and the six risk component scores).

    No estimated_cost, physical_progress, expected_completion, or
    geographic data is used, since none of that is populated for real
    Phase 2 rows. Anomaly does not mean fraud -- these are advisory,
    review-priority signals only.

    Only projects that trigger at least one rule are queried (never the
    full 56,323-row table); the resulting candidate alerts are sorted
    deterministically and paginated in memory via skip/limit.
    """
    generated_at = datetime.now(timezone.utc)

    candidate_projects = db.query(Project).filter(_build_candidate_filter()).all()

    raw_alerts: List[dict] = []
    for p in candidate_projects:
        raw_alerts.extend(_generate_alerts_for_project(p, generated_at))

    # Deterministic sort: severity priority, then risk_score desc, then project_id.
    raw_alerts.sort(
        key=lambda a: (
            SEVERITY_PRIORITY.get(a["severity"], 99),
            -a["sort_score"],
            a["project_id"],
        )
    )

    page = raw_alerts[skip: skip + limit]

    return [
        AlertOut(
            alert_id=a["alert_id"],
            project_id=a["project_id"],
            alert_type=a["alert_type"],
            severity=a["severity"],
            message=a["message"],
            created_at=generated_at,
        )
        for a in page
    ]