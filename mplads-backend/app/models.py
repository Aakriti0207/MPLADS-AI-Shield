"""
SQLAlchemy models for the MPLADS AI backend.

Day 1 scope: a single `projects` table only. Related tables
(project_progress, project_payments, alerts, risk_scores,
duplicate_matches) are intentionally deferred to later phases.
"""

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Numeric,
    String,
)
from sqlalchemy.sql import func

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    # --- Identity -----------------------------------------------------
    # MPLADS project IDs are alphanumeric codes assigned by the source
    # system, not auto-incrementing integers, so they're a natural
    # primary key. unique=True + index=True gives fast lookups for
    # GET /projects/{id}.
    project_id = Column(String(50), primary_key=True, unique=True, index=True)

    # --- Location / jurisdiction ---------------------------------------
    # Indexed because dashboard stats and future filtering will commonly
    # group/filter by state, district, and constituency.
    state = Column(String(100), nullable=False, index=True)
    district = Column(String(100), nullable=False, index=True)
    constituency = Column(String(100), nullable=True, index=True)
    mp_name = Column(String(150), nullable=True)

    # --- Project classification -----------------------------------------
    work_type = Column(String(150), nullable=True, index=True)
    implementing_agency = Column(String(200), nullable=True)

    # --- Financials -------------------------------------------------
    # Numeric (fixed-point) rather than Float to avoid floating-point
    # rounding errors on monetary values. Precision 14, scale 2 comfortably
    # covers amounts up to ~10^12 with paise/rupee-level accuracy.
    sanctioned_amount = Column(Numeric(14, 2), nullable=True)
    estimated_cost = Column(Numeric(14, 2), nullable=True)
    expenditure = Column(Numeric(14, 2), nullable=True)

    # --- Progress ---------------------------------------------------
    # Represented consistently as a percentage (0-100) using Numeric(5, 2),
    # so both fields share the same scale and can be directly compared
    # (e.g. for future payment-progress mismatch detection).
    financial_progress = Column(Numeric(5, 2), nullable=True)
    physical_progress = Column(Numeric(5, 2), nullable=True)

    # --- Timeline -----------------------------------------------------
    # Plain Date (no time component) since MPLADS milestones are tracked
    # by calendar date, not time-of-day.
    sanction_date = Column(Date, nullable=True)
    start_date = Column(Date, nullable=True)
    expected_completion = Column(Date, nullable=True)
    actual_completion = Column(Date, nullable=True)

    # --- Geolocation --------------------------------------------------
    # Numeric(9, 6) gives ~11cm precision at the equator, standard for
    # lat/lng storage, and avoids float drift.
    latitude = Column(Numeric(9, 6), nullable=True)
    longitude = Column(Numeric(9, 6), nullable=True)

    # --- Status ---------------------------------------------------------
    # Indexed: dashboard stats will frequently group/count by status
    # (e.g. Ongoing / Completed / Delayed).
    status = Column(String(50), nullable=True, index=True)

    # --- Record-keeping -------------------------------------------------
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Project project_id={self.project_id!r} status={self.status!r}>"
