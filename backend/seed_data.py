"""
Seed script: inserts synthetic, demonstration-only MPLADS-like project
records into the `projects` table for local development and to give
the future ML/risk engine meaningful examples to work with.

*** IMPORTANT ***
All records generated here are SYNTHETIC. They are NOT real MPLADS /
government data and must never be represented or described as such
anywhere downstream (UI, reports, docs, etc.). State/district/
constituency names are real (so the data looks geographically
plausible), but the project details, amounts, agencies, and MPs are
fabricated for demo purposes only.

Design notes:
    - Uses the exact fields defined on app.models.Project - nothing
      extra is added to the table itself.
    - A handful of records are intentionally constructed to look
      suspicious (cost overruns, payment/progress mismatches, long
      delays, unusually high costs) so that later phases (ML risk
      engine) have real examples to detect. No "is_anomaly" or
      ground-truth label column is added to the `projects` table -
      that would leak future model answers into production-shaped
      data. If/when a labelled evaluation set is needed, it should
      live in its own separate table/file (e.g. a future
      `risk_eval_labels` table), not here.
    - Idempotent: running this script multiple times will not create
      duplicate rows. It upserts by `project_id` (deletes any existing
      seed rows with the same IDs first, then inserts fresh).

Run with: python seed_data.py
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from app.database import SessionLocal
from app.models import Project

random.seed(42)  # reproducible synthetic data across runs

# --- Reference pools for realistic-looking (but fabricated) data ----------

STATES_DISTRICTS_CONSTITUENCIES = [
    ("Uttar Pradesh", "Lucknow", "Lucknow"),
    ("Uttar Pradesh", "Varanasi", "Varanasi"),
    ("Uttar Pradesh", "Kanpur Nagar", "Kanpur"),
    ("Maharashtra", "Pune", "Pune"),
    ("Maharashtra", "Nagpur", "Nagpur"),
    ("Maharashtra", "Mumbai Suburban", "Mumbai North"),
    ("Bihar", "Patna", "Patna Sahib"),
    ("Bihar", "Gaya", "Gaya"),
    ("West Bengal", "Kolkata", "Kolkata Dakshin"),
    ("West Bengal", "Howrah", "Howrah"),
    ("Tamil Nadu", "Chennai", "Chennai Central"),
    ("Tamil Nadu", "Coimbatore", "Coimbatore"),
    ("Karnataka", "Bengaluru Urban", "Bangalore South"),
    ("Karnataka", "Mysuru", "Mysore"),
    ("Rajasthan", "Jaipur", "Jaipur"),
    ("Rajasthan", "Jodhpur", "Jodhpur"),
    ("Gujarat", "Ahmedabad", "Ahmedabad East"),
    ("Gujarat", "Surat", "Surat"),
    ("Madhya Pradesh", "Bhopal", "Bhopal"),
    ("Madhya Pradesh", "Indore", "Indore"),
    ("Punjab", "Amritsar", "Amritsar"),
    ("Kerala", "Ernakulam", "Ernakulam"),
    ("Odisha", "Khordha", "Bhubaneswar"),
    ("Assam", "Kamrup Metropolitan", "Guwahati"),
    ("Telangana", "Hyderabad", "Hyderabad"),
]

# Approximate real district-centre coordinates for geographic plausibility
# (city-level accuracy only - fine for synthetic demo data).
DISTRICT_COORDS = {
    "Lucknow": (26.8467, 80.9462),
    "Varanasi": (25.3176, 82.9739),
    "Kanpur Nagar": (26.4499, 80.3319),
    "Pune": (18.5204, 73.8567),
    "Nagpur": (21.1458, 79.0882),
    "Mumbai Suburban": (19.0760, 72.8777),
    "Patna": (25.5941, 85.1376),
    "Gaya": (24.7955, 84.9994),
    "Kolkata": (22.5726, 88.3639),
    "Howrah": (22.5958, 88.2636),
    "Chennai": (13.0827, 80.2707),
    "Coimbatore": (11.0168, 76.9558),
    "Bengaluru Urban": (12.9716, 77.5946),
    "Mysuru": (12.2958, 76.6394),
    "Jaipur": (26.9124, 75.7873),
    "Jodhpur": (26.2389, 73.0243),
    "Ahmedabad": (23.0225, 72.5714),
    "Surat": (21.1702, 72.8311),
    "Bhopal": (23.2599, 77.4126),
    "Indore": (22.7196, 75.8577),
    "Amritsar": (31.6340, 74.8723),
    "Ernakulam": (9.9816, 76.2999),
    "Khordha": (20.2961, 85.8245),
    "Kamrup Metropolitan": (26.1445, 91.7362),
    "Hyderabad": (17.3850, 78.4867),
}

MP_NAMES = [
    "R. Sharma", "A. Verma", "S. Reddy", "K. Nair", "M. Singh",
    "P. Iyer", "D. Patel", "N. Gupta", "T. Rao", "J. Das",
]

WORK_TYPES = [
    "Road Construction",
    "Drinking Water Supply",
    "Community Hall Construction",
    "School Building Renovation",
    "Solar Street Lighting",
    "Drainage System",
    "Public Toilet Complex",
    "Sports Infrastructure",
    "Library Building",
    "Health Sub-Centre Upgrade",
]

AGENCIES = [
    "District Rural Development Agency",
    "Public Works Department",
    "Municipal Corporation",
    "Zilla Parishad",
    "State Electricity Board",
    "Jal Nigam",
    "Panchayati Raj Department",
]

STATUSES = ["Sanctioned", "Ongoing", "Completed"]


def jitter_coord(lat: float, lng: float, spread: float = 0.15) -> tuple:
    """Add small random jitter so projects in the same district aren't
    all stacked on the exact same point."""
    return (
        round(lat + random.uniform(-spread, spread), 6),
        round(lng + random.uniform(-spread, spread), 6),
    )


def random_date(start: date, end: date) -> date:
    delta_days = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta_days, 0)))


def build_normal_project(idx: int) -> Project:
    state, district, constituency = random.choice(STATES_DISTRICTS_CONSTITUENCIES)
    base_lat, base_lng = DISTRICT_COORDS[district]
    lat, lng = jitter_coord(base_lat, base_lng)

    estimated_cost = Decimal(random.randrange(500_000, 4_000_000, 50_000))
    # Normal case: sanctioned amount close to estimated cost, expenditure
    # a reasonable fraction of sanctioned amount.
    sanctioned_amount = estimated_cost
    status = random.choice(STATUSES)

    sanction_date = random_date(date(2022, 1, 1), date(2024, 6, 30))
    start_date = sanction_date + timedelta(days=random.randint(15, 60))
    expected_completion = start_date + timedelta(days=random.randint(120, 365))

    if status == "Completed":
        physical_progress = Decimal("100.00")
        financial_progress = Decimal(str(round(random.uniform(90, 100), 2)))
        actual_completion = expected_completion - timedelta(days=random.randint(-20, 30))
        expenditure = (sanctioned_amount * financial_progress / Decimal(100)).quantize(Decimal("0.01"))
    else:
        physical_progress = Decimal(str(round(random.uniform(5, 85), 2)))
        # Keep financial progress reasonably close to physical progress
        # (normal, non-suspicious case).
        financial_progress = (
            physical_progress + Decimal(str(round(random.uniform(-8, 8), 2)))
        ).quantize(Decimal("0.01"))
        financial_progress = max(Decimal("0.00"), min(financial_progress, Decimal("100.00")))
        actual_completion = None
        expenditure = (sanctioned_amount * financial_progress / Decimal(100)).quantize(Decimal("0.01"))

    return Project(
        project_id=f"MP{idx:04d}",
        state=state,
        district=district,
        constituency=constituency,
        mp_name=random.choice(MP_NAMES),
        work_type=random.choice(WORK_TYPES),
        implementing_agency=random.choice(AGENCIES),
        sanctioned_amount=sanctioned_amount,
        estimated_cost=estimated_cost,
        expenditure=expenditure,
        financial_progress=financial_progress,
        physical_progress=physical_progress,
        sanction_date=sanction_date,
        start_date=start_date,
        expected_completion=expected_completion,
        actual_completion=actual_completion,
        latitude=Decimal(str(lat)),
        longitude=Decimal(str(lng)),
        status=status,
    )


def build_suspicious_projects(start_idx: int) -> list:
    """
    A handful of deliberately anomalous-looking records so the future
    ML/risk engine has real positive examples to detect:
        1. Expenditure far exceeding estimated cost.
        2. Financial progress much higher than physical progress.
        3. Badly delayed completion (still "Ongoing" long past deadline).
        4. Unusually high project cost for its work type.

    No label/flag column is stored on these rows - they are only
    distinguishable by their data values, same as a real anomaly would
    be. Keep any ground-truth mapping (which project_ids are the
    planted anomalies) in your own separate notes/eval file, not in
    this table.
    """
    suspicious = []
    idx = start_idx

    # 1. Expenditure >> estimated cost (cost overrun / possible fund misuse)
    state, district, constituency = STATES_DISTRICTS_CONSTITUENCIES[0]
    lat, lng = jitter_coord(*DISTRICT_COORDS[district])
    estimated_cost = Decimal("1200000.00")
    suspicious.append(Project(
        project_id=f"MP{idx:04d}",
        state=state, district=district, constituency=constituency,
        mp_name=random.choice(MP_NAMES),
        work_type="Road Construction",
        implementing_agency="Public Works Department",
        sanctioned_amount=Decimal("1200000.00"),
        estimated_cost=estimated_cost,
        expenditure=Decimal("2150000.00"),  # ~79% over estimate
        financial_progress=Decimal("100.00"),
        physical_progress=Decimal("70.00"),
        sanction_date=date(2023, 2, 10),
        start_date=date(2023, 3, 1),
        expected_completion=date(2023, 12, 31),
        actual_completion=None,
        latitude=Decimal(str(lat)), longitude=Decimal(str(lng)),
        status="Ongoing",
    ))
    idx += 1

    # 2. Financial progress much higher than physical progress
    state, district, constituency = STATES_DISTRICTS_CONSTITUENCIES[3]
    lat, lng = jitter_coord(*DISTRICT_COORDS[district])
    suspicious.append(Project(
        project_id=f"MP{idx:04d}",
        state=state, district=district, constituency=constituency,
        mp_name=random.choice(MP_NAMES),
        work_type="Community Hall Construction",
        implementing_agency="Zilla Parishad",
        sanctioned_amount=Decimal("900000.00"),
        estimated_cost=Decimal("900000.00"),
        expenditure=Decimal("810000.00"),
        financial_progress=Decimal("90.00"),
        physical_progress=Decimal("30.00"),  # 60-point gap
        sanction_date=date(2023, 4, 5),
        start_date=date(2023, 5, 1),
        expected_completion=date(2024, 1, 31),
        actual_completion=None,
        latitude=Decimal(str(lat)), longitude=Decimal(str(lng)),
        status="Ongoing",
    ))
    idx += 1

    # 3. Badly delayed - still "Ongoing" long past expected completion
    state, district, constituency = STATES_DISTRICTS_CONSTITUENCIES[6]
    lat, lng = jitter_coord(*DISTRICT_COORDS[district])
    suspicious.append(Project(
        project_id=f"MP{idx:04d}",
        state=state, district=district, constituency=constituency,
        mp_name=random.choice(MP_NAMES),
        work_type="Drainage System",
        implementing_agency="Municipal Corporation",
        sanctioned_amount=Decimal("650000.00"),
        estimated_cost=Decimal("650000.00"),
        expenditure=Decimal("400000.00"),
        financial_progress=Decimal("62.00"),
        physical_progress=Decimal("45.00"),
        sanction_date=date(2021, 6, 1),
        start_date=date(2021, 7, 15),
        expected_completion=date(2022, 6, 30),  # over 2 years overdue
        actual_completion=None,
        latitude=Decimal(str(lat)), longitude=Decimal(str(lng)),
        status="Ongoing",
    ))
    idx += 1

    # 4. Unusually high cost for its work type (e.g. a "Public Toilet
    #    Complex" that costs as much as a much larger project)
    state, district, constituency = STATES_DISTRICTS_CONSTITUENCIES[12]
    lat, lng = jitter_coord(*DISTRICT_COORDS[district])
    suspicious.append(Project(
        project_id=f"MP{idx:04d}",
        state=state, district=district, constituency=constituency,
        mp_name=random.choice(MP_NAMES),
        work_type="Public Toilet Complex",
        implementing_agency="Municipal Corporation",
        sanctioned_amount=Decimal("3800000.00"),  # ~10x typical for this work type
        estimated_cost=Decimal("3800000.00"),
        expenditure=Decimal("1900000.00"),
        financial_progress=Decimal("50.00"),
        physical_progress=Decimal("48.00"),
        sanction_date=date(2023, 8, 1),
        start_date=date(2023, 9, 1),
        expected_completion=date(2024, 6, 30),
        actual_completion=None,
        latitude=Decimal(str(lat)), longitude=Decimal(str(lng)),
        status="Ongoing",
    ))
    idx += 1

    # 5. Combined anomaly: high cost overrun + delay + progress mismatch
    state, district, constituency = STATES_DISTRICTS_CONSTITUENCIES[16]
    lat, lng = jitter_coord(*DISTRICT_COORDS[district])
    suspicious.append(Project(
        project_id=f"MP{idx:04d}",
        state=state, district=district, constituency=constituency,
        mp_name=random.choice(MP_NAMES),
        work_type="School Building Renovation",
        implementing_agency="Panchayati Raj Department",
        sanctioned_amount=Decimal("1500000.00"),
        estimated_cost=Decimal("1500000.00"),
        expenditure=Decimal("2400000.00"),  # 60% over
        financial_progress=Decimal("95.00"),
        physical_progress=Decimal("40.00"),  # big mismatch
        sanction_date=date(2022, 3, 1),
        start_date=date(2022, 4, 1),
        expected_completion=date(2023, 3, 31),  # well overdue
        actual_completion=None,
        latitude=Decimal(str(lat)), longitude=Decimal(str(lng)),
        status="Ongoing",
    ))
    idx += 1

    return suspicious


def seed(total_normal: int = 35) -> None:
    db = SessionLocal()
    try:
        normal_projects = [build_normal_project(i) for i in range(1, total_normal + 1)]
        suspicious_projects = build_suspicious_projects(total_normal + 1)
        all_projects = normal_projects + suspicious_projects

        project_ids = [p.project_id for p in all_projects]

        # Idempotent re-seed: remove any existing rows with these IDs
        # first, so running this script again doesn't create duplicates
        # or fail on a primary-key conflict.
        deleted = (
            db.query(Project)
            .filter(Project.project_id.in_(project_ids))
            .delete(synchronize_session=False)
        )
        if deleted:
            print(f"Removed {deleted} existing seed row(s) before re-inserting.")

        db.add_all(all_projects)
        db.commit()

        print(
            f"Seeded {len(all_projects)} synthetic project records "
            f"({len(normal_projects)} normal, {len(suspicious_projects)} "
            "intentionally suspicious-looking)."
        )
        print(
            "NOTE: This is synthetic demonstration data only - it does "
            "not represent real MPLADS / government records."
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
