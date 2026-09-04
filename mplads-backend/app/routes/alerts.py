"""
Routes for alerts.

*** TEMPORARY / MOCK IMPLEMENTATION ***

There is no `alerts` table yet - it will be introduced once the ML
risk engine exists to actually generate alerts (cost anomalies,
payment-vs-progress mismatches, delays, duplicate works, etc.), per
the project's eventual data flow.

For Day 1, this endpoint returns a small hardcoded list of mock alerts
so the React dashboard has something realistic to build against. The
response_model (AlertOut) is the real contract we intend the eventual
alerts table/risk engine to satisfy - only the data source changes
later (hardcoded list -> `SELECT * FROM alerts` via SQLAlchemy), not
the shape callers receive.

TODO (future phase): replace MOCK_ALERTS with a real `Alert` SQLAlchemy
model + `alerts` table, and query it here via the get_db dependency,
the same way app/routes/projects.py does.
"""

from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter

from app.schemas import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])

_now = datetime.now(timezone.utc)

# Hardcoded mock data - NOT read from the database. Illustrates the
# kinds of alerts the eventual ML risk engine will generate, per the
# project brief: cost anomalies, payment/physical-progress mismatches,
# delays, and possible duplicate works.
MOCK_ALERTS: List[AlertOut] = [
    AlertOut(
        alert_id="ALERT-0001",
        project_id="MP001",
        alert_type="cost_anomaly",
        severity="high",
        message=(
            "Estimated cost is significantly higher than the median cost "
            "for similar 'Road Construction' works in this district."
        ),
        created_at=_now - timedelta(days=2),
    ),
    AlertOut(
        alert_id="ALERT-0002",
        project_id="MP002",
        alert_type="payment_progress_mismatch",
        severity="medium",
        message=(
            "Financial progress (25%) is well ahead of physical progress "
            "(20%) - expenditure may be outpacing actual work done."
        ),
        created_at=_now - timedelta(days=1),
    ),
    AlertOut(
        alert_id="ALERT-0003",
        project_id="MP002",
        alert_type="delay",
        severity="medium",
        message="Expected completion date has passed but the project is still marked 'Ongoing'.",
        created_at=_now - timedelta(hours=6),
    ),
    AlertOut(
        alert_id="ALERT-0004",
        project_id="MP003",
        alert_type="possible_duplicate",
        severity="low",
        message=(
            "A project with a similar work description and nearby "
            "coordinates already exists in this constituency."
        ),
        created_at=_now - timedelta(hours=1),
    ),
]


@router.get("", response_model=List[AlertOut])
def list_alerts():
    """
    Return mock alerts.

    *** MOCK DATA - not read from the database. ***
    Will be replaced with a real query against an `alerts` table once
    the ML risk engine exists to populate it.
    """
    return MOCK_ALERTS
