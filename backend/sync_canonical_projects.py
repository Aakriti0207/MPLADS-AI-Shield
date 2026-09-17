"""Synchronize PostgreSQL projects with canonical_projects.csv.

Phase 1 - Data Integrity & Foundation.

Safety properties:
- canonical work_id is the authoritative project identity.
- Existing DB-only projects are NEVER deleted.
- Existing risk/XAI fields are preserved on matched rows.
- Only non-null canonical values overwrite core DB fields.
- MP zero-padding differences (MP1 <-> MP001) are treated as the same ID.
- Primary-key renames are performed only when there is exactly one safe match.
- A persistent SQL backup table is created before mutation.
- --dry-run performs no writes.
- All writes occur in one transaction; failures roll back the mutation.

Run from backend/:
    python sync_canonical_projects.py --dry-run
    python sync_canonical_projects.py

Optional:
    python sync_canonical_projects.py --canonical path/to/canonical_projects.csv
    python sync_canonical_projects.py --risk path/to/project_risk_scores.csv
    python sync_canonical_projects.py --no-backup   # only if a separate DB backup exists
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.database import SessionLocal, engine
from app.models import Project

DEFAULT_CANONICAL = Path(__file__).resolve().parent / "data" / "processed" / "canonical_projects.csv"
DEFAULT_RISK = Path(__file__).resolve().parent / "data" / "phase2" / "project_risk_scores.csv"
BATCH_SIZE = 1000

# Canonical fields are authoritative when present. Values absent from canonical
# are intentionally not used to erase a value already present in PostgreSQL.
CORE_FIELDS = {
    "state": "state",
    "district": "district",
    "constituency": "constituency",
    "mp": "mp_name",
    "work_category": "work_type",
    "implementing_agency": "implementing_agency",
    "sanction_amount": "sanctioned_amount",
    "total_expenditure": "expenditure",
    "sanction_date": "sanction_date",
    "completion_date": "actual_completion",
    "status": "status",
    "elected_nominated": "elected_nominated",
}

# Risk/XAI fields are only used for a brand-new canonical row when a matching
# risk CSV row exists. For an existing DB row they are preserved unchanged.
RISK_FIELDS = (
    "risk_score",
    "risk_level",
    "financial_risk_score",
    "payment_risk_score",
    "execution_risk_score",
    "peer_anomaly_score",
    "isolation_forest_score",
    "anomaly_risk_score",
    "duplicate_risk_score",
    "raw_max_similarity",
    "most_similar_work_id",
    "risk_reason_1",
    "risk_reason_2",
    "risk_reason_3",
    "risk_metadata",
)


def clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        if not v or v.lower() in {"nan", "none", "null", "nat"}:
            return None
        return v
    return value


def canonicalize_id(value: Any) -> str | None:
    value = clean(value)
    if value is None:
        return None
    value = str(value).strip()
    # Only normalize leading zeroes in the MP numeric component.
    return re.sub(r"(?<=/MP)0+(?=\d+/)", "", value)


def parse_decimal(value: Any, scale: int = 2) -> Decimal | None:
    value = clean(value)
    if value is None:
        return None
    try:
        d = Decimal(str(value))
        quantum = Decimal("1") if scale == 0 else Decimal("1." + "0" * scale)
        return d.quantize(quantum)
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_date(value: Any) -> date | None:
    value = clean(value)
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_bool(value: Any) -> bool | None:
    value = clean(value)
    if value is None:
        return None
    return str(value).lower() in {"1", "true", "yes", "y"}


def parse_risk_metadata(row: dict[str, Any]) -> dict[str, Any] | None:
    # Preserve useful diagnostic fields from the old risk snapshot without
    # inventing any new risk value.
    str_fields = ("work_category", "work_status", "data_source_flag", "project_size_bucket", "peer_group_tier")
    int_fields = (
        "n_expenditure_transactions", "n_distinct_vendors", "n_payment_success",
        "n_payment_inprogress", "elapsed_duration_days", "project_duration_days",
        "n_components_available",
    )
    float_fields = (
        "financial_utilization", "expenditure_vs_sanction", "mp_allocated_limit",
        "negative_amount_score", "vendor_concentration_score", "rapid_disbursement_score",
        "slow_disbursement_pace_score", "payment_stall_score", "expenditure_without_sanction_score",
        "elapsed_percentile_in_peer_group",
    )
    bool_fields = ("has_sanction_record", "has_completion_record", "has_expenditure_record")
    meta: dict[str, Any] = {}
    for field in str_fields:
        v = clean(row.get(field))
        if v is not None:
            meta[field] = str(v)
    for field in int_fields:
        v = clean(row.get(field))
        if v is not None:
            try:
                meta[field] = int(round(float(v)))
            except (ValueError, TypeError):
                pass
    for field in float_fields:
        v = clean(row.get(field))
        if v is not None:
            try:
                meta[field] = float(v)
            except (ValueError, TypeError):
                pass
    for field in bool_fields:
        v = parse_bool(row.get(field))
        if v is not None:
            meta[field] = v
    return meta or None


def canonical_values(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for source, dest in CORE_FIELDS.items():
        raw = row.get(source)
        if source in {"sanction_amount", "total_expenditure"}:
            value = parse_decimal(raw, 2)
        elif source in {"sanction_date", "completion_date"}:
            value = parse_date(raw)
        else:
            value = clean(raw)
        if value is not None:
            out[dest] = value
    out["is_synthetic"] = False
    return out


def risk_values(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in RISK_FIELDS:
        raw = row.get(field)
        if field == "risk_level" or field.startswith("risk_reason") or field == "most_similar_work_id":
            value = clean(raw)
        elif field == "risk_metadata":
            value = parse_risk_metadata(row)
        elif field == "raw_max_similarity":
            value = parse_decimal(raw, 4)
        else:
            value = parse_decimal(raw, 2)
        if value is not None:
            out[field] = value
    return out


def load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def build_unique_map(rows: list[dict[str, Any]], id_field: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    mapping: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for row in rows:
        raw_id = clean(row.get(id_field))
        norm = canonicalize_id(raw_id)
        if not norm:
            continue
        if norm in mapping:
            duplicates.append(norm)
        else:
            mapping[norm] = row
    return mapping, duplicates


def backup_projects(connection) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    table = f"projects_phase1_backup_{stamp}"
    connection.execute(text(f'CREATE TABLE "{table}" AS TABLE projects'))
    return table


def get_project_rows(session) -> dict[str, Project]:
    return {str(p.project_id).strip(): p for p in session.query(Project).all()}


def validate_no_fk_references() -> None:
    inspector = inspect(engine)
    refs = []
    for table in inspector.get_table_names():
        for fk in inspector.get_foreign_keys(table):
            if fk.get("referred_table") == "projects":
                refs.append((table, fk.get("constrained_columns"), fk.get("referred_columns")))
    if refs:
        raise RuntimeError(f"Aborting: foreign keys reference projects: {refs}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--risk", type=Path, default=DEFAULT_RISK)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    if not args.canonical.exists():
        print(f"ERROR: canonical file not found: {args.canonical}")
        return 2

    canonical_rows = load_csv(args.canonical)
    canonical_map, canonical_dupes = build_unique_map(canonical_rows, "work_id")
    if canonical_dupes:
        print(f"ERROR: canonical has {len(set(canonical_dupes))} duplicate normalized work_id values.")
        print("First duplicates:", sorted(set(canonical_dupes))[:20])
        return 2

    risk_map: dict[str, dict[str, Any]] = {}
    if args.risk.exists():
        risk_rows = load_csv(args.risk)
        risk_map, risk_dupes = build_unique_map(risk_rows, "work_id")
        if risk_dupes:
            print(f"WARNING: ignoring duplicate normalized risk IDs: {len(set(risk_dupes))}")
    else:
        print(f"INFO: risk CSV not found; new canonical rows will have no risk/XAI fields: {args.risk}")

    validate_no_fk_references()

    session = SessionLocal()
    try:
        db_rows = get_project_rows(session)
        db_exact = {pid: pid for pid in db_rows}
        db_norm: dict[str, str] = {}
        collisions: dict[str, list[str]] = {}
        for pid in db_rows:
            norm = canonicalize_id(pid)
            if norm is None:
                continue
            if norm in db_norm and db_norm[norm] != pid:
                collisions.setdefault(norm, [db_norm[norm]]).append(pid)
            else:
                db_norm[norm] = pid
        if collisions:
            print(f"ERROR: DB contains {len(collisions)} normalized-ID collisions; refusing to guess.")
            for norm, ids in list(collisions.items())[:20]:
                print(" ", norm, "=>", ids)
            return 2

        canonical_norms = set(canonical_map)
        db_norms = set(db_norm)
        common_norms = canonical_norms & db_norms
        canonical_only = sorted(canonical_norms - db_norms)
        db_only = sorted(db_norms - canonical_norms)
        exact_common = sum(1 for norm in common_norms if canonical_map[norm].get("work_id", "").strip() == db_norm[norm])
        format_only = len(common_norms) - exact_common

        print("=== PHASE 1 CANONICAL SYNCHRONIZATION ===")
        print(f"Canonical rows:                 {len(canonical_map):,}")
        print(f"DB rows:                        {len(db_rows):,}")
        print(f"Common after ID normalization: {len(common_norms):,}")
        print(f"Exact ID matches:               {exact_common:,}")
        print(f"Format-only ID matches:         {format_only:,}")
        print(f"Canonical-only rows to insert:  {len(canonical_only):,}")
        print(f"DB-only rows to retain:         {len(db_only):,}")

        if args.dry_run:
            print("\nDRY RUN: no database writes performed.")
            print("Sample ID migrations:")
            shown = 0
            for norm in sorted(common_norms):
                old = db_norm[norm]
                new = str(canonical_map[norm]["work_id"]).strip()
                if old != new:
                    print(f"  {old} -> {new}")
                    shown += 1
                    if shown >= 20:
                        break
            print("Sample canonical-only IDs:")
            for norm in canonical_only[:20]:
                print(" ", canonical_map[norm]["work_id"])
            return 0

        if not args.no_backup:
            backup_name = backup_projects(session.connection())
            print(f"Backup table created: {backup_name}")
        else:
            print("WARNING: --no-backup supplied; proceeding without persistent DB backup table.")

        renamed = 0
        updated = 0
        inserted = 0
        preserved_db_only = len(db_only)

        # Rename format-only IDs first. There are no DB foreign keys pointing
        # at projects (validated above), and canonical exact IDs are disjoint
        # from format-only old IDs under the normalized uniqueness check.
        for norm in sorted(common_norms):
            old_id = db_norm[norm]
            new_id = str(canonical_map[norm]["work_id"]).strip()
            if old_id != new_id:
                # Guard against an existing exact canonical key.
                if new_id in db_rows and new_id != old_id:
                    raise RuntimeError(f"ID collision while renaming {old_id} -> {new_id}")
                project = db_rows[old_id]
                project.project_id = new_id
                db_rows[new_id] = project
                del db_rows[old_id]
                renamed += 1

        # Update matched projects with non-null canonical core values only.
        for norm in sorted(common_norms):
            canonical_id = str(canonical_map[norm]["work_id"]).strip()
            project = db_rows[canonical_id]
            values = canonical_values(canonical_map[norm])
            changed = False
            for field, value in values.items():
                if field == "project_id":
                    continue
                if value is not None and getattr(project, field) != value:
                    setattr(project, field, value)
                    changed = True
            if changed:
                updated += 1

        # Insert canonical-only projects. Risk/XAI is populated only when a
        # matching risk snapshot row exists; otherwise it stays NULL.
        for norm in canonical_only:
            row = canonical_map[norm]
            work_id = str(row["work_id"]).strip()
            values = canonical_values(row)
            values["project_id"] = work_id
            values.update(risk_values(risk_map[norm]) if norm in risk_map else {})
            session.add(Project(**values))
            inserted += 1
            if inserted % BATCH_SIZE == 0:
                session.flush()

        session.commit()

        # Post-commit verification from a fresh query.
        verify_session = SessionLocal()
        try:
            final_ids = {str(x[0]).strip() for x in verify_session.query(Project.project_id).all()}
            missing_exact = sorted(set(canonical_map) - {canonicalize_id(x) for x in final_ids})
            duplicates_after = len(final_ids) != verify_session.query(Project.project_id).count()
            print("\n=== SYNCHRONIZATION RESULT ===")
            print(f"ID renames:                    {renamed:,}")
            print(f"Existing rows updated:         {updated:,}")
            print(f"Canonical rows inserted:       {inserted:,}")
            print(f"DB-only rows retained:         {preserved_db_only:,}")
            print(f"Canonical normalized IDs missing after sync: {len(missing_exact):,}")
            print(f"Duplicate project IDs after sync:           {duplicates_after}")
            if missing_exact:
                print("First missing normalized IDs:")
                print("\n".join(missing_exact[:20]))
                return 1
            if duplicates_after:
                return 1
        finally:
            verify_session.close()

        print("\nSUCCESS: canonical project identity and core fields are synchronized.")
        print("DB-only legacy projects were retained; existing risk/XAI fields were preserved.")
        return 0

    except Exception as exc:
        session.rollback()
        print(f"ERROR: transaction rolled back: {exc}")
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
