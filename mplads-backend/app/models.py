"""
SQLAlchemy models for the MPLADS AI backend.

Day 1 scope: a single `projects` table only. Related tables
(project_progress, project_payments, alerts, risk_scores,
duplicate_matches) are intentionally deferred to later phases.

Phase 2 addition (see docs/phase2_handoff equivalent context in
import_phase2.py): the real Phase 2 ML risk-scoring output
(project_risk_scores.csv, 56,323 real projects, work_id-keyed) is
imported additively into this same table. The Phase 2 risk fields
below are an ADVISORY PRIORITIZATION SIGNAL for human review, NOT a
fraud label or verdict - see import_phase2.py and the Phase 2
project's own docs/phase2_handoff.md for why these are framed as
review-priority signals rather than conclusions.

Real Phase 2 rows have no source value for district, estimated_cost,
physical_progress, start_date, expected_completion, latitude, or
longitude - those columns are left NULL for such rows rather than
fabricated (see import_phase2.py's transform_row()).
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Numeric,
    String,
    Text,
    false,
)
from sqlalchemy.sql import func

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    # --- Identity -----------------------------------------------------
    # MPLADS project IDs are alphanumeric codes assigned by the source
    # system, not auto-incrementing integers, so they're a natural
    # primary key. unique=True + index=True gives fast lookups for
    # GET /projects/{id}. Real Phase 2 work_ids (e.g.
    # "WS/MP001/2023-2024/103702") are at most 27 characters, well
    # within String(50).
    project_id = Column(String(50), primary_key=True, unique=True, index=True)

    # --- Location / jurisdiction ---------------------------------------
    # Indexed because dashboard stats and future filtering will commonly
    # group/filter by state, district, and constituency.
    #
    # Phase 2 note: state and district are nullable (changed from Day 1's
    # nullable=False) because ~41% of real Phase 2 projects have no state
    # value in the source snapshot, and the Phase 2 dataset has no district
    # column at all - district is NULL for every Phase-2-imported row.
    # Never fabricate either field; leave NULL when there's no source value.
    state = Column(String(100), nullable=True, index=True)
    district = Column(String(100), nullable=True, index=True)
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
    #
    # Phase 2 note: real Phase 2 rows do NOT populate this field. The
    # Phase 2 CSV's closest analogue, `work_status`, uses a different,
    # non-equivalent vocabulary (e.g. "Physical Inspection", "Vendor
    # Identification") that the Phase 2 project's own handoff notes flag
    # as potentially stale relative to other snapshots. Silently
    # crosswalking it into this field's Sanctioned/Ongoing/Completed
    # vocabulary would be a fabricated mapping, not a verified one, so it
    # is intentionally left NULL for Phase-2-imported rows. The raw
    # work_status value is preserved as-is in risk_metadata for
    # reference. See import_phase2.py for details.
    status = Column(String(50), nullable=True, index=True)

    # --- Phase 2: ML risk-scoring output (advisory, not a fraud label) --
    # Populated by import_phase2.py from the real project_risk_scores.csv
    # output. All fields here are nullable because they only apply to
    # projects that have gone through the Phase 2 risk pipeline; rows
    # seeded by seed_data.py (is_synthetic=True) leave these NULL.
    #
    # elected_nominated: "Elected MP" / "Nominated MP", partial coverage
    # (complementary to `constituency` - each real row typically has one
    # or the other, not both, per the source snapshots).
    elected_nominated = Column(String(20), nullable=True)

    # is_synthetic distinguishes demonstration data (seed_data.py) from
    # real imported MPLADS data (import_phase2.py). Defaults to False at
    # both the ORM and DB level; seed_data.py explicitly sets it to True
    # and import_phase2.py explicitly sets it to False, so the default is
    # a safety net rather than the primary source of truth.
    is_synthetic = Column(Boolean, nullable=False, default=False, server_default=false())

    # Overall risk score (0-100-ish scale; observed range in the Phase 2
    # snapshot is 0-68.5) and its categorical tier. Advisory prioritization
    # signal for human review - NOT a fraud determination.
    risk_score = Column(Numeric(5, 2), nullable=True, index=True)
    risk_level = Column(String(20), nullable=True, index=True)

    # Risk sub-scores that combine into risk_score above. Each is only
    # populated when the underlying data components needed to compute it
    # were available for that project (see risk_metadata's
    # n_components_available / data_source_flag for why a given sub-score
    # may be NULL for a specific project).
    financial_risk_score = Column(Numeric(5, 2), nullable=True)
    payment_risk_score = Column(Numeric(5, 2), nullable=True)
    execution_risk_score = Column(Numeric(5, 2), nullable=True)
    peer_anomaly_score = Column(Numeric(5, 2), nullable=True)
    isolation_forest_score = Column(Numeric(5, 2), nullable=True)
    anomaly_risk_score = Column(Numeric(5, 2), nullable=True)
    duplicate_risk_score = Column(Numeric(5, 2), nullable=True)

    # Possible-duplicate-work detection: highest text/feature similarity
    # found against any other project, and which project that was.
    # raw_max_similarity is a 0-1 fraction (e.g. 0.1716), not a percentage.
    raw_max_similarity = Column(Numeric(5, 4), nullable=True)
    most_similar_work_id = Column(String(50), nullable=True)

    # Up to three short, human-readable explanations for the risk score
    # (free text sentences from the Phase 2 pipeline, e.g. "Expenditure is
    # recorded for this project but no matching sanction record exists in
    # this snapshot."). Extremely sparse in the current snapshot (present
    # for only a handful of projects) - most rows leave these NULL.
    risk_reason_1 = Column(Text, nullable=True)
    risk_reason_2 = Column(Text, nullable=True)
    risk_reason_3 = Column(Text, nullable=True)

    # Catch-all for the remaining Phase 2 CSV columns that don't warrant
    # their own dedicated column (e.g. work_category, work_status,
    # data_source_flag, n_distinct_vendors, project_size_bucket,
    # peer_group_tier, and similar diagnostic/component fields). Keeping
    # these as JSON avoids a wide, mostly-diagnostic schema while still
    # preserving the full Phase 2 signal for anyone who needs it. See
    # import_phase2.py's build_risk_metadata() for the exact key list.
    risk_metadata = Column(JSON, nullable=True)

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
