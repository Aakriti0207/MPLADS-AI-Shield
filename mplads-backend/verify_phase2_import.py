"""
Verify that import_phase2.py imported project_risk_scores.csv correctly.

Run with:
    python verify_phase2_import.py
    python verify_phase2_import.py --csv path/to/other_file.csv

Checks performed (each printed as PASS/FAIL):
    1. Row count: the number of real (is_synthetic=False) rows in the
       `projects` table matches both the CSV's unique work_id count and
       the expected 56,323.
    2. No duplicate project_id in the database, and no duplicate work_id
       in the source CSV.
    3. risk_score is populated (non-NULL) and matches the source CSV, for
       a random sample of rows.
    4. Nullable fields remain nullable and are never fabricated:
       state's NULL count matches the CSV exactly; district and the other
       no-source fields (estimated_cost, physical_progress, start_date,
       expected_completion, latitude, longitude) are NULL for every
       Phase-2-imported row.
    5. A random sample of imported rows matches the source CSV field-by-
       field (reuses import_phase2.transform_row(), so the check can
       never silently drift from what the importer actually does).

Idempotency itself isn't something this script can check from a single
snapshot of the database - it's a property of running import_phase2.py
twice and confirming the counts above don't change. See the Part 1 test
report for that comparison; this script is what "run verification" (step
4 of the test plan) refers to.

Exit code is 0 if every check passes, 1 otherwise.
"""

import csv
import random
import sys
from pathlib import Path

from sqlalchemy import func

from app.database import SessionLocal
from app.models import Project
from import_phase2 import DEFAULT_CSV_PATH, transform_row, _clean

EXPECTED_ROW_COUNT = 56323
SAMPLE_SIZE_RISK_SCORE = 500
SAMPLE_SIZE_SPOT_CHECK = 200

# Fields with no CSV source at all - must be NULL for every imported row.
NEVER_SOURCED_FIELDS = (
    "estimated_cost",
    "physical_progress",
    "start_date",
    "expected_completion",
    "latitude",
    "longitude",
)

# Fields checked directly against transform_row()'s output in the spot check.
SPOT_CHECK_STR_FIELDS = (
    "state",
    "constituency",
    "mp_name",
    "implementing_agency",
    "elected_nominated",
    "risk_level",
    "most_similar_work_id",
    "risk_reason_1",
    "risk_reason_2",
    "risk_reason_3",
)
SPOT_CHECK_DATE_FIELDS = ("sanction_date", "actual_completion")
SPOT_CHECK_NUMERIC_FIELDS = (
    "sanctioned_amount",
    "expenditure",
    "financial_progress",
    "risk_score",
    "financial_risk_score",
    "payment_risk_score",
    "execution_risk_score",
    "peer_anomaly_score",
    "isolation_forest_score",
    "duplicate_risk_score",
    "anomaly_risk_score",
    "raw_max_similarity",
)

_all_passed = True


def check(name: str, condition: bool, details: str = "") -> bool:
    global _all_passed
    status = "PASS" if condition else "FAIL"
    suffix = f" -- {details}" if details else ""
    print(f"[{status}] {name}{suffix}")
    if not condition:
        _all_passed = False
    return condition


def load_csv_rows(csv_path: Path) -> list:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def numeric_close(a, b, tol=0.01) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol


def run(csv_path: Path) -> int:
    rows = load_csv_rows(csv_path)
    csv_by_id = {r["work_id"]: r for r in rows if (r.get("work_id") or "").strip()}
    csv_unique_ids = list(csv_by_id.keys())

    db = SessionLocal()
    try:
        print(f"Loaded {len(rows)} CSV rows ({len(csv_unique_ids)} unique work_ids) from {csv_path}\n")

        # --- 1. Row count ---------------------------------------------
        db_count = (
            db.query(func.count(Project.project_id))
            .filter(Project.is_synthetic.is_(False))
            .scalar()
        )
        check(
            "DB row count (is_synthetic=False) matches CSV unique work_id count",
            db_count == len(csv_unique_ids),
            f"db={db_count} csv_unique={len(csv_unique_ids)}",
        )
        check(
            "DB row count matches expected 56,323",
            db_count == EXPECTED_ROW_COUNT,
            f"db={db_count} expected={EXPECTED_ROW_COUNT}",
        )

        # --- 2. No duplicates -------------------------------------------
        total = db.query(func.count(Project.project_id)).scalar()
        distinct = db.query(func.count(func.distinct(Project.project_id))).scalar()
        check("No duplicate project_id in the database", total == distinct, f"total={total} distinct={distinct}")

        csv_dupes = len(rows) - len(csv_unique_ids)
        check("No duplicate work_id in the source CSV", csv_dupes == 0, f"duplicate_rows={csv_dupes}")

        # --- 3. risk_score populated & matches source (sample) -----------
        sample_ids = random.sample(csv_unique_ids, min(SAMPLE_SIZE_RISK_SCORE, len(csv_unique_ids)))
        null_risk = 0
        risk_mismatches = []
        missing_from_db = []
        for pid in sample_ids:
            proj = db.get(Project, pid)
            if proj is None:
                missing_from_db.append(pid)
                continue
            csv_val_raw = csv_by_id[pid].get("risk_score")
            csv_val = round(float(csv_val_raw), 2) if _clean(csv_val_raw) is not None else None
            db_val = float(proj.risk_score) if proj.risk_score is not None else None

            if proj.risk_score is None:
                null_risk += 1
            # FIX: a NULL in the DB where the CSV has a real value is itself
            # a mismatch -- it must NOT be silently skipped via `continue`.
            # The old code did `continue` here, which meant a row that was
            # 100% wrong (NULL instead of a real score) never reached the
            # comparison below, so it could never be counted as a mismatch.
            # That is exactly how "0 mismatches" was reported while every
            # single sampled row actually had the wrong (NULL) value.
            if not numeric_close(csv_val, db_val):
                risk_mismatches.append((pid, csv_val, db_val))

        check(
            f"Sampled work_ids exist in the database (n={len(sample_ids)})",
            len(missing_from_db) == 0,
            f"missing={missing_from_db[:5]}",
        )
        check(
            "risk_score is populated (non-NULL) for sampled rows",
            null_risk == 0,
            f"{null_risk} of {len(sample_ids)} sampled rows had NULL risk_score",
        )
        check(
            "risk_score matches the source CSV for sampled rows "
            "(NULL-vs-real-value counts as a mismatch)",
            len(risk_mismatches) == 0,
            f"{len(risk_mismatches)} mismatches, e.g. {risk_mismatches[:3]}",
        )

        # --- 3b. FULL population check across all real projects, not just
        # a sample -- counts non-NULL risk_score/risk_level over every
        # is_synthetic=False row and compares against the CSV, plus a full
        # per-row value comparison (not merely a count comparison, since
        # equal counts alone couldn't catch e.g. right total but wrong rows).
        db_rows = (
            db.query(Project.project_id, Project.risk_score, Project.risk_level)
            .filter(Project.is_synthetic.is_(False))
            .all()
        )
        db_by_id = {pid: (score, level) for pid, score, level in db_rows}

        csv_non_null_risk_score = sum(
            1 for r in rows if _clean(r.get("risk_score")) is not None
        )
        csv_non_null_risk_level = sum(
            1 for r in rows if _clean(r.get("risk_level")) is not None
        )
        db_non_null_risk_score = sum(1 for (score, _level) in db_by_id.values() if score is not None)
        db_non_null_risk_level = sum(1 for (_score, level) in db_by_id.values() if level is not None)

        check(
            f"FULL POPULATION: non-NULL risk_score count matches CSV (n={len(csv_unique_ids)})",
            db_non_null_risk_score == csv_non_null_risk_score,
            f"db_non_null={db_non_null_risk_score} csv_non_null={csv_non_null_risk_score}",
        )
        check(
            f"FULL POPULATION: non-NULL risk_level count matches CSV (n={len(csv_unique_ids)})",
            db_non_null_risk_level == csv_non_null_risk_level,
            f"db_non_null={db_non_null_risk_level} csv_non_null={csv_non_null_risk_level}",
        )

        full_score_mismatches = []
        full_level_mismatches = []
        for pid, csv_row in csv_by_id.items():
            db_entry = db_by_id.get(pid)
            db_score, db_level = (None, None) if db_entry is None else db_entry

            csv_score_raw = csv_row.get("risk_score")
            csv_score = round(float(csv_score_raw), 2) if _clean(csv_score_raw) is not None else None
            db_score_f = float(db_score) if db_score is not None else None
            if not numeric_close(csv_score, db_score_f):
                full_score_mismatches.append((pid, csv_score, db_score_f))

            csv_level = _clean(csv_row.get("risk_level"))
            if csv_level != db_level:
                full_level_mismatches.append((pid, csv_level, db_level))

        check(
            f"FULL POPULATION: risk_score matches CSV for every row (n={len(csv_unique_ids)})",
            len(full_score_mismatches) == 0,
            f"{len(full_score_mismatches)} mismatches, e.g. {full_score_mismatches[:5]}",
        )
        check(
            f"FULL POPULATION: risk_level matches CSV for every row (n={len(csv_unique_ids)})",
            len(full_level_mismatches) == 0,
            f"{len(full_level_mismatches)} mismatches, e.g. {full_level_mismatches[:5]}",
        )

        # --- 4. Nullable fields stay nullable / no fabrication -----------
        csv_null_state = sum(1 for r in rows if not (r.get("state") or "").strip())
        db_null_state = (
            db.query(func.count(Project.project_id))
            .filter(Project.is_synthetic.is_(False), Project.state.is_(None))
            .scalar()
        )
        check(
            "state NULL-count matches the CSV exactly (none fabricated)",
            db_null_state == csv_null_state,
            f"db_null={db_null_state} csv_null={csv_null_state}",
        )

        db_district_populated = (
            db.query(func.count(Project.project_id))
            .filter(Project.is_synthetic.is_(False), Project.district.isnot(None))
            .scalar()
        )
        check(
            "district is NULL for every Phase 2 row (no source column exists)",
            db_district_populated == 0,
            f"non_null_count={db_district_populated}",
        )

        for field_name in NEVER_SOURCED_FIELDS:
            column = getattr(Project, field_name)
            non_null_count = (
                db.query(func.count(Project.project_id))
                .filter(Project.is_synthetic.is_(False), column.isnot(None))
                .scalar()
            )
            check(
                f"{field_name} is NULL for every Phase 2 row (no source column exists)",
                non_null_count == 0,
                f"non_null_count={non_null_count}",
            )

        # --- 5. Spot-check full field mapping against the source ---------
        spot_ids = random.sample(csv_unique_ids, min(SAMPLE_SIZE_SPOT_CHECK, len(csv_unique_ids)))
        mismatches = []
        for pid in spot_ids:
            proj = db.get(Project, pid)
            if proj is None:
                mismatches.append((pid, "missing_from_db", None, None))
                continue
            expected = transform_row(csv_by_id[pid])

            for field in SPOT_CHECK_STR_FIELDS:
                actual = getattr(proj, field)
                if actual != expected[field]:
                    mismatches.append((pid, field, expected[field], actual))

            for field in SPOT_CHECK_DATE_FIELDS:
                actual = getattr(proj, field)
                if actual != expected[field]:
                    mismatches.append((pid, field, expected[field], actual))

            for field in SPOT_CHECK_NUMERIC_FIELDS:
                actual = getattr(proj, field)
                exp = expected[field]
                actual_f = float(actual) if actual is not None else None
                exp_f = float(exp) if exp is not None else None
                if not numeric_close(exp_f, actual_f, tol=0.005):
                    mismatches.append((pid, field, exp, actual))

            if proj.risk_metadata != expected["risk_metadata"]:
                mismatches.append((pid, "risk_metadata", expected["risk_metadata"], proj.risk_metadata))

        check(
            f"Spot-check: sampled rows match source CSV field-by-field (n={len(spot_ids)})",
            len(mismatches) == 0,
            f"{len(mismatches)} field mismatches, e.g. {mismatches[:5]}",
        )

    finally:
        db.close()

    print()
    if _all_passed:
        print("ALL CHECKS PASSED")
        return 0
    print("SOME CHECKS FAILED - see above")
    return 1


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Verify the Phase 2 CSV import.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV_PATH)
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: CSV not found at {args.csv}", file=sys.stderr)
        sys.exit(1)

    sys.exit(run(args.csv))
