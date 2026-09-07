"""
Import the real Phase 2 ML risk-scoring output into the `projects` table.

Source: data/phase2/project_risk_scores.csv - the real Phase 2 pipeline
output, 56,323 rows x 49 columns, `work_id` as the unique project key.

Run with:
    python import_phase2.py
    python import_phase2.py --csv path/to/other_file.csv   # override path

What this script does:
    1. Makes sure the `projects` table has the Phase 2 columns (calls
       app.schema_migration.sync_schema() first, so this is safe to run
       against a database that hasn't been migrated yet).
    2. Reads the CSV and, for each row, maps it onto the `Project` model
       (see transform_row() below for the exact field-by-field mapping
       and build_risk_metadata() for everything that lands in the
       risk_metadata JSON catch-all).
    3. Upserts by `work_id` -> `project_id`: new work_ids are inserted,
       existing ones are updated in place. Nothing is ever duplicated.
    4. Prints a report: total rows read, new projects imported, existing
       projects updated, invalid rows.

Idempotency:
    Running this script again on the same (or an updated) CSV re-applies
    the same Phase-2-sourced fields to the same rows - it does not create
    duplicates, and does not touch fields that have no Phase 2 CSV source
    (district, estimated_cost, physical_progress, start_date,
    expected_completion, latitude, longitude, status - see "Fields
    intentionally left alone" below).

Mapping decisions worth calling out explicitly (see the Part 1 task brief
for the full rationale):
    - financial_utilization (a 0-1 fraction) * 100 -> financial_progress.
    - completion_date -> actual_completion. expected_completion is NEVER
      set from this data - there is no target-date source in the Phase 2
      snapshot.
    - ida -> implementing_agency, verbatim. No regex-parsing of ida to
      guess a district.
    - district, estimated_cost, physical_progress, start_date,
      expected_completion, latitude, longitude: the CSV has no source
      column for any of these, so they are NEVER set here. They stay
      NULL on insert and are left untouched on update.
    - work_status is NOT mapped to the existing `status` field: the two
      use different, non-equivalent vocabularies (see app/models.py's
      `status` column comment), so status is also left untouched. The
      raw work_status value is preserved in risk_metadata instead.
    - is_synthetic is always set to False here (this is real data, never
      the seed_data.py demo data).
"""

import argparse
import csv
import logging
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

from app.database import SessionLocal, engine
from app.models import Project
from app.schema_migration import sync_schema

logger = logging.getLogger("mplads.import_phase2")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

DEFAULT_CSV_PATH = Path(__file__).resolve().parent / "data" / "phase2" / "project_risk_scores.csv"

BATCH_SIZE = 2000

# --- CSV columns that get folded into the risk_metadata JSON catch-all ----
# (everything else either has its own dedicated Project column, or - for
# work_status specifically - is deliberately not carried into `status`;
# it's preserved here for reference instead.)
_META_STR_FIELDS = (
    "work_category",
    "work_status",
    "data_source_flag",
    "project_size_bucket",
    "peer_group_tier",
)
_META_INT_FIELDS = (
    "n_expenditure_transactions",
    "n_distinct_vendors",
    "n_payment_success",
    "n_payment_inprogress",
    "elapsed_duration_days",
    "project_duration_days",
    "n_components_available",
)
_META_FLOAT_FIELDS = (
    "financial_utilization",  # raw 0-1 fraction, kept alongside the *100 copy in financial_progress
    "expenditure_vs_sanction",
    "mp_allocated_limit",
    "negative_amount_score",
    "vendor_concentration_score",
    "rapid_disbursement_score",
    "slow_disbursement_pace_score",
    "payment_stall_score",
    "expenditure_without_sanction_score",
    "elapsed_percentile_in_peer_group",
)
_META_BOOL_FIELDS = (
    "has_sanction_record",
    "has_completion_record",
    "has_expenditure_record",
)


# --- Small, defensive CSV value parsers ------------------------------------
# The CSV represents missing values as empty strings (csv.DictReader never
# hands us a real NaN - that's a pandas concept). These treat "", "nan",
# and "none" (any case) all as "no value", and never raise on bad input -
# a malformed value becomes None rather than crashing the whole import.

def _clean(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    raw = raw.strip()
    if raw == "" or raw.lower() in ("nan", "none", "null"):
        return None
    return raw


def parse_str(raw: Optional[str]) -> Optional[str]:
    return _clean(raw)


def parse_float(raw: Optional[str]) -> Optional[float]:
    raw = _clean(raw)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse_int(raw: Optional[str]) -> Optional[int]:
    value = parse_float(raw)
    if value is None:
        return None
    return int(round(value))


def parse_bool(raw: Optional[str]) -> Optional[bool]:
    raw = _clean(raw)
    if raw is None:
        return None
    return raw.strip().lower() in ("true", "1", "yes")


def parse_date(raw: Optional[str]) -> Optional[date]:
    raw = _clean(raw)
    if raw is None:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        logger.warning("Unparseable date %r; leaving NULL.", raw)
        return None


def to_decimal(value: Optional[float], ndigits: int = 2) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(round(float(value), ndigits)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def build_risk_metadata(row: dict) -> dict:
    """Everything from the CSV that doesn't get its own Project column."""
    meta: dict[str, Any] = {}
    for field in _META_STR_FIELDS:
        value = parse_str(row.get(field))
        if value is not None:
            meta[field] = value
    for field in _META_INT_FIELDS:
        value = parse_int(row.get(field))
        if value is not None:
            meta[field] = value
    for field in _META_FLOAT_FIELDS:
        value = parse_float(row.get(field))
        if value is not None:
            meta[field] = value
    for field in _META_BOOL_FIELDS:
        value = parse_bool(row.get(field))
        if value is not None:
            meta[field] = value
    return meta


def transform_row(row: dict) -> Optional[dict]:
    """
    Map one CSV row onto the Project columns this import script owns.

    Returns None for an invalid row (no work_id). Returns a dict of
    {column_name: value} otherwise - deliberately containing ONLY the
    columns this script is authoritative for (see module docstring's
    "Fields intentionally left alone"), so callers never accidentally
    clobber a field this CSV has no source for.
    """
    work_id = parse_str(row.get("work_id"))
    if not work_id:
        return None

    financial_utilization = parse_float(row.get("financial_utilization"))
    financial_progress = (
        to_decimal(financial_utilization * 100, 2) if financial_utilization is not None else None
    )

    return {
        "project_id": work_id,
        "state": parse_str(row.get("state")),
        "constituency": parse_str(row.get("constituency")),
        "mp_name": parse_str(row.get("mp_name_clean")),
        "implementing_agency": parse_str(row.get("ida")),  # verbatim, no district parsing
        "sanctioned_amount": to_decimal(parse_float(row.get("sanction_amount")), 2),
        "expenditure": to_decimal(parse_float(row.get("total_expenditure")), 2),
        "financial_progress": financial_progress,
        "sanction_date": parse_date(row.get("sanction_date")),
        "actual_completion": parse_date(row.get("completion_date")),
        "elected_nominated": parse_str(row.get("elected_nominated")),
        "is_synthetic": False,
        "risk_score": to_decimal(parse_float(row.get("risk_score")), 2),
        "risk_level": parse_str(row.get("risk_level")),
        "financial_risk_score": to_decimal(parse_float(row.get("financial_risk_score")), 2),
        "payment_risk_score": to_decimal(parse_float(row.get("payment_risk_score")), 2),
        "execution_risk_score": to_decimal(parse_float(row.get("execution_risk_score")), 2),
        "peer_anomaly_score": to_decimal(parse_float(row.get("peer_anomaly_score")), 2),
        "isolation_forest_score": to_decimal(parse_float(row.get("isolation_forest_score")), 2),
        "duplicate_risk_score": to_decimal(parse_float(row.get("duplicate_risk_score")), 2),
        "anomaly_risk_score": to_decimal(parse_float(row.get("anomaly_risk_score")), 2),
        "raw_max_similarity": to_decimal(parse_float(row.get("raw_max_similarity")), 4),
        "most_similar_work_id": parse_str(row.get("most_similar_work_id")),
        "risk_reason_1": parse_str(row.get("risk_reason_1")),
        "risk_reason_2": parse_str(row.get("risk_reason_2")),
        "risk_reason_3": parse_str(row.get("risk_reason_3")),
        "risk_metadata": build_risk_metadata(row),
    }
    # Deliberately NOT set here (no CSV source - never fabricated):
    #   district, estimated_cost, physical_progress, start_date,
    #   expected_completion, latitude, longitude, status


def import_csv(csv_path: Path, batch_size: int = BATCH_SIZE) -> dict:
    sync_schema(engine)

    db = SessionLocal()
    try:
        existing_ids = {pid for (pid,) in db.query(Project.project_id).all()}

        total_rows = 0
        invalid_rows = 0
        duplicate_in_file = 0
        seen_in_file = set()
        to_insert = []
        to_update = []

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_rows += 1
                fields = transform_row(row)
                if fields is None:
                    invalid_rows += 1
                    logger.warning("Row %d has no work_id; skipping.", total_rows)
                    continue

                project_id = fields["project_id"]
                if project_id in seen_in_file:
                    duplicate_in_file += 1
                    logger.warning(
                        "work_id %r appears more than once in this CSV; "
                        "last occurrence wins.",
                        project_id,
                    )
                seen_in_file.add(project_id)

                if project_id in existing_ids:
                    to_update.append(fields)
                else:
                    to_insert.append(fields)
                    existing_ids.add(project_id)  # avoid double-insert on an in-file repeat

        for i in range(0, len(to_insert), batch_size):
            db.bulk_insert_mappings(Project, to_insert[i : i + batch_size])
        for i in range(0, len(to_update), batch_size):
            db.bulk_update_mappings(Project, to_update[i : i + batch_size])

        db.commit()

        report = {
            "total_rows_read": total_rows,
            "new_projects_imported": len(to_insert),
            "existing_projects_updated": len(to_update),
            "invalid_rows": invalid_rows,
            "duplicate_work_ids_in_file": duplicate_in_file,
        }
        return report
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import the real Phase 2 project_risk_scores.csv into the projects table."
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help=f"Path to project_risk_scores.csv (default: {DEFAULT_CSV_PATH})",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: CSV not found at {args.csv}", file=sys.stderr)
        return 1

    report = import_csv(args.csv)

    print("Phase 2 import complete:")
    print(f"  total rows read:            {report['total_rows_read']}")
    print(f"  new projects imported:      {report['new_projects_imported']}")
    print(f"  existing projects updated:  {report['existing_projects_updated']}")
    print(f"  invalid rows:               {report['invalid_rows']}")
    if report["duplicate_work_ids_in_file"]:
        print(f"  duplicate work_ids in file: {report['duplicate_work_ids_in_file']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
