"""
Pydantic schemas for the MPLADS AI backend.

Day 1 scope: response schema(s) for the `projects` endpoints only.

Phase 2 update: `ProjectOut` now exposes the Phase 2 ML risk-scoring
fields that already exist as columns on the `Project` model / `projects`
table (populated by import_phase2.py from project_risk_scores.csv). No
new fields were invented here -- every field added below has a matching
Column on `Project` in app/models.py. Types and nullability mirror that
model exactly:
  - Numeric(5, 2) / Numeric(5, 4) columns  -> Optional[Decimal]
  - String / Text columns                  -> Optional[str]
  - JSON column (risk_metadata)            -> Optional[dict]
All of them are nullable because they only apply to projects that have
gone through the Phase 2 pipeline (and even then, several sub-scores are
only populated when the underlying data components were available for
that specific project -- see risk_metadata's n_components_available).
These are an advisory risk-prioritization signal for human review, NOT a
fraud determination -- see app/models.py's Phase 2 docstring.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# --- Authentication -----------------------------------------------------
# Added alongside JWT authentication. Kept in this same module rather
# than a separate file since the project doesn't otherwise split
# schemas.py by resource.

class RegisterRequest(BaseModel):
    """Request body for POST /auth/register."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(min_length=1, max_length=50)


class LoginRequest(BaseModel):
    """Request body for POST /auth/login."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response body for a successful login."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Safe, public-facing user profile. Never includes password_hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime


class ProjectOut(BaseModel):
    """Response shape for a single project, mirroring the `projects` table.

    NOTE (Phase 2): `state` and `district` are Optional here, matching the
    `Project` model's nullable=True (real Phase 2 projects can lack a state
    value, and none of them have a district value at all - see
    app/models.py).

    Phase 2 risk fields (risk_score, risk_level, and the rest below) are
    now part of the response contract, sourced directly from the matching
    columns on `Project`. Nothing here is computed or fabricated by this
    schema -- it only reflects what's already stored in the database.
    """

    model_config = ConfigDict(from_attributes=True)

    project_id: str
    state: Optional[str] = None
    district: Optional[str] = None
    constituency: Optional[str] = None
    mp_name: Optional[str] = None
    work_type: Optional[str] = None
    implementing_agency: Optional[str] = None

    sanctioned_amount: Optional[Decimal] = None
    estimated_cost: Optional[Decimal] = None
    expenditure: Optional[Decimal] = None

    financial_progress: Optional[Decimal] = None
    physical_progress: Optional[Decimal] = None

    sanction_date: Optional[date] = None
    start_date: Optional[date] = None
    expected_completion: Optional[date] = None
    actual_completion: Optional[date] = None

    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

    status: Optional[str] = None

    # --- Phase 2: ML risk-scoring output (advisory, not a fraud label) --
    # Mirrors app/models.py's Project columns of the same names, in the
    # same order, so the two stay easy to diff against each other.
    risk_score: Optional[Decimal] = None
    risk_level: Optional[str] = None

    financial_risk_score: Optional[Decimal] = None
    payment_risk_score: Optional[Decimal] = None
    execution_risk_score: Optional[Decimal] = None
    peer_anomaly_score: Optional[Decimal] = None
    isolation_forest_score: Optional[Decimal] = None
    anomaly_risk_score: Optional[Decimal] = None
    duplicate_risk_score: Optional[Decimal] = None

    raw_max_similarity: Optional[Decimal] = None
    most_similar_work_id: Optional[str] = None

    risk_reason_1: Optional[str] = None
    risk_reason_2: Optional[str] = None
    risk_reason_3: Optional[str] = None

    # JSON catch-all (work_category, work_status, data_source_flag,
    # n_distinct_vendors, project_size_bucket, peer_group_tier, etc. --
    # see import_phase2.py's build_risk_metadata() for the exact keys).
    # Typed as a plain dict since its values are a mix of str/int/float/bool.
    risk_metadata: Optional[dict[str, Any]] = None

    created_at: datetime
    updated_at: datetime


class ByStateStat(BaseModel):
    """One row of the Phase 3E state-level aggregate."""

    state: str
    total_sanctioned_amount: Decimal
    total_expenditure: Decimal


class ByWorkTypeStat(BaseModel):
    """One row of the Phase 3E work-type aggregate."""

    work_type: str
    count: int


class DashboardStats(BaseModel):
    """Aggregate statistics computed live from the `projects` table."""

    total_projects: int
    total_sanctioned_amount: Decimal
    total_expenditure: Decimal
    average_financial_progress: Optional[Decimal] = None
    average_physical_progress: Optional[Decimal] = None
    active_projects: int
    completed_projects: int
    delayed_projects: int

    # Phase 3C addition: real counts of projects per Phase 2 risk_level
    # (LOW/MEDIUM/HIGH/CRITICAL), grouped straight from the Project table.
    # Nothing here is computed/fabricated -- it's a GROUP BY count over the
    # same risk_level column already populated by the Phase 2 import.
    # A risk_level value that is legitimately NULL (unscored) is omitted
    # from this dict rather than being folded into any bucket.
    risk_level_counts: Optional[dict[str, int]] = None

    # Phase 3E additions: real, small aggregates for the Analytics page.
    # Both are straight GROUP BY queries over existing Project columns --
    # no new table, no per-project data, no invented metrics. NULL/blank
    # state and work_type are grouped under "Not specified" rather than
    # dropped or silently merged into another bucket.
    by_state: Optional[list[ByStateStat]] = None
    by_work_type: Optional[list[ByWorkTypeStat]] = None


class AlertOut(BaseModel):
    """
    Response shape for a single alert.

    Alerts are dynamically generated from real, DB-derived project risk
    data (see app/routes/alerts.py) -- there is no separate `alerts`
    table, and nothing in this response is mock/placeholder data.
    """

    alert_id: str
    project_id: str
    alert_type: str
    severity: str
    message: str
    created_at: datetime