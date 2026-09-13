"""
ML-1: populate/update Project.status from the current Phase 2 canonical
dataset (data/processed/canonical_projects.csv).

TEMPORARY COMPATIBILITY BRIDGE -- NOT A REGENERATED RISK PIPELINE

This script ONLY updates Project.status from the current canonical dataset.
It does NOT read or modify project_risk_scores.csv or any risk-score fields.

Important identity compatibility:
    Canonical Phase 2 IDs may contain MP1, MP2, ... while the existing
    database may contain MP001, MP002, ...

    Example:
        WS/MP1/2023-2024/103702
        WS/MP001/2023-2024/103702

    These are treated as the same logical project for matching purposes,
    but the actual database project_id is preserved exactly as stored.

Run:
    python import_canonical_status.py --dry-run
    python import_canonical_status.py
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path
from typing import Optional

from app.database import SessionLocal, engine
from app.models import Project
from app.schema_migration import sync_schema


logger = logging.getLogger("mplads.import_canonical_status")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


DEFAULT_CANONICAL_CSV_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "processed"
    / "canonical_projects.csv"
)

BATCH_SIZE = 2000

VALID_STATUSES = frozenset(
    {
        "COMPLETED",
        "ONGOING",
        "SANCTIONED",
        "RECOMMENDED",
        "NOT_SPECIFIED",
    }
)


def _clean(raw: Optional[str]) -> Optional[str]:
    """Normalize blank/null CSV values to None."""
    if raw is None:
        return None

    raw = raw.strip()

    if raw == "" or raw.lower() in ("nan", "none", "null"):
        return None

    return raw


def _normalize_work_id(work_id: str) -> str:
    """
    Normalize the MP numeric component.

    Examples:
        WS/MP1/2023-2024/103702
            -> WS/MP001/2023-2024/103702

        WS/MP001/2023-2024/103702
            -> WS/MP001/2023-2024/103702

    Only the matching key is normalized.
    The actual database Project.project_id is NEVER changed.
    """
    parts = work_id.split("/")

    if len(parts) >= 2 and parts[1].startswith("MP"):
        number = parts[1][2:]

        if number.isdigit():
            parts[1] = f"MP{int(number):03d}"

    return "/".join(parts)


def load_canonical_statuses(
    csv_path: Path,
) -> tuple[dict[str, str], list[str], int]:
    """
    Read canonical_projects.csv.

    Returns:
        canonical status map:
            normalized_work_id -> status

        duplicate canonical work IDs

        number of rows without resolved status
    """

    seen: dict[str, int] = {}
    statuses: dict[str, Optional[str]] = {}

    rows_with_no_status = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError(f"{csv_path} has no header")

        if "work_id" not in reader.fieldnames:
            raise ValueError(f"{csv_path} has no work_id column")

        if "status" not in reader.fieldnames:
            raise ValueError(
                f"{csv_path} has no status column. "
                "Regenerate canonical_projects.csv using the ML-1 canonical pipeline."
            )

        for row in reader:
            raw_work_id = _clean(row.get("work_id"))

            if not raw_work_id:
                continue

            work_id = _normalize_work_id(raw_work_id)

            status = _clean(row.get("status"))

            seen[work_id] = seen.get(work_id, 0) + 1

            if status is None:
                rows_with_no_status += 1

            statuses[work_id] = status

    duplicates = sorted(
        work_id
        for work_id, count in seen.items()
        if count > 1
    )

    # Never guess when duplicate canonical identities exist.
    clean_map = {
        work_id: status
        for work_id, status in statuses.items()
        if seen[work_id] == 1
    }

    for work_id in duplicates:
        clean_map.pop(work_id, None)

    return clean_map, duplicates, rows_with_no_status


def build_status_update_plan(
    canonical_statuses: dict[str, str],
    db_projects: dict[str, str],
) -> dict:
    """
    Build a pure update plan.

    db_projects maps:
        normalized_project_id -> actual_database_project_id

    This is important because normalized IDs must NEVER be written back
    into the database as Project.project_id.
    """

    matched: dict[str, tuple[str, str]] = {}

    unmatched_canonical: list[str] = []
    unresolved_status: list[str] = []

    for normalized_work_id, status in canonical_statuses.items():

        if status is None:
            unresolved_status.append(normalized_work_id)
            continue

        if status not in VALID_STATUSES:
            logger.warning(
                "Unexpected status value %r for %r; skipping.",
                status,
                normalized_work_id,
            )
            continue

        actual_db_id = db_projects.get(normalized_work_id)

        if actual_db_id is not None:
            matched[normalized_work_id] = (
                actual_db_id,
                status,
            )
        else:
            unmatched_canonical.append(normalized_work_id)

    db_without_canonical_status = sorted(
        normalized_id
        for normalized_id in db_projects
        if normalized_id not in canonical_statuses
    )

    return {
        "matched": matched,
        "unmatched_canonical": sorted(unmatched_canonical),
        "unresolved_status": sorted(unresolved_status),
        "db_without_canonical_status": db_without_canonical_status,
    }


def apply_status_updates(
    db,
    matched: dict[str, tuple[str, str]],
    batch_size: int = BATCH_SIZE,
) -> int:
    """
    Update ONLY Project.status.

    The actual database project_id is used for the update.
    """

    mappings = [
        {
            "project_id": actual_db_id,
            "status": status,
        }
        for actual_db_id, status in matched.values()
    ]

    for i in range(0, len(mappings), batch_size):
        db.bulk_update_mappings(
            Project,
            mappings[i : i + batch_size],
        )

    return len(mappings)


def run(csv_path: Path, dry_run: bool) -> dict:

    (
        canonical_statuses,
        duplicates,
        rows_with_no_status,
    ) = load_canonical_statuses(csv_path)

    if not dry_run:
        sync_schema(engine)

    db = SessionLocal()

    try:

        # normalized_project_id -> actual DB project_id
        db_projects: dict[str, str] = {}

        normalization_collisions: dict[str, list[str]] = {}

        rows = db.query(Project.project_id).all()

        for (project_id,) in rows:

            if not project_id:
                continue

            normalized_id = _normalize_work_id(project_id)

            if normalized_id in db_projects:
                normalization_collisions.setdefault(
                    normalized_id,
                    [db_projects[normalized_id]],
                ).append(project_id)
            else:
                db_projects[normalized_id] = project_id

        if normalization_collisions:
            raise ValueError(
                "Database identity collision detected after MP normalization. "
                "No updates were applied."
            )

        plan = build_status_update_plan(
            canonical_statuses,
            db_projects,
        )

        updated_count = 0

        if not dry_run and plan["matched"]:

            updated_count = apply_status_updates(
                db,
                plan["matched"],
            )

            db.commit()

        return {
            "csv_path": str(csv_path),
            "dry_run": dry_run,
            "canonical_rows_total": (
                len(canonical_statuses) + len(duplicates)
            ),
            "canonical_duplicate_work_ids": duplicates,
            "canonical_rows_with_no_status": rows_with_no_status,
            "db_projects_total": len(db_projects),
            "matched_count": len(plan["matched"]),
            "updated_count": updated_count,
            "unmatched_canonical_count": len(
                plan["unmatched_canonical"]
            ),
            "unmatched_canonical_sample": (
                plan["unmatched_canonical"][:10]
            ),
            "db_without_canonical_status_count": len(
                plan["db_without_canonical_status"]
            ),
            "db_without_canonical_status_sample": (
                plan["db_without_canonical_status"][:10]
            ),
        }

    except Exception:

        db.rollback()
        raise

    finally:

        db.close()


def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Populate Project.status from the current Phase 2 "
            "canonical dataset. "
            "Does NOT read project_risk_scores.csv."
        )
    )

    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CANONICAL_CSV_PATH,
        help=(
            "Path to canonical_projects.csv "
            f"(default: {DEFAULT_CANONICAL_CSV_PATH})"
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing to the database.",
    )

    args = parser.parse_args()

    if not args.csv.exists():

        print(
            f"ERROR: canonical CSV not found at {args.csv}",
            file=sys.stderr,
        )

        return 1

    report = run(
        args.csv,
        dry_run=args.dry_run,
    )

    mode = (
        "DRY RUN (no changes written)"
        if report["dry_run"]
        else "APPLIED"
    )

    print()
    print(f"ML-1 canonical status import -- {mode}")
    print(f"  source:                              {report['csv_path']}")
    print(
        f"  canonical rows read:                  "
        f"{report['canonical_rows_total']}"
    )
    print(
        f"  duplicate canonical work_ids found:   "
        f"{len(report['canonical_duplicate_work_ids'])}"
    )
    print(
        f"  canonical rows with no resolved status:"
        f"{report['canonical_rows_with_no_status']:>8}"
    )
    print(
        f"  DB projects (total):                  "
        f"{report['db_projects_total']}"
    )
    print(
        f"  matched (canonical & in DB):           "
        f"{report['matched_count']}"
    )

    verb = (
        "would be updated"
        if report["dry_run"]
        else "updated"
    )

    print(
        f"  status fields {verb}:                  "
        f"{report['updated_count']}"
    )

    print(
        f"  unmatched canonical records (not in DB): "
        f"{report['unmatched_canonical_count']}"
    )

    for work_id in report["unmatched_canonical_sample"]:
        print(f"    - {work_id}")

    print(
        f"  DB projects with no canonical status:  "
        f"{report['db_without_canonical_status_count']}"
    )

    for work_id in report["db_without_canonical_status_sample"]:
        print(f"    - {work_id}")

    print()
    print(
        "IMPORTANT: Only Project.status is updated. "
        "Risk-score fields remain untouched."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())