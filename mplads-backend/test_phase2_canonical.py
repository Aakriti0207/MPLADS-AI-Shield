"""
Phase 2 validation script.

Kept at the backend root, not inside ml/, for the same reason as
test_phase1_preprocessing.py: this validates ml.canonical, it isn't
part of the canonical-building pipeline itself.

Run with: python test_phase2_canonical.py
"""

import json
import re

from ml.canonical import build_canonical_dataset, write_outputs
from ml.config import BACKEND_ROOT, WORK_ID_PATTERN

OUTPUT_DIR = BACKEND_ROOT / "data" / "processed"

PRECOMPUTED_RISK_COLUMNS = {
    "risk_score", "risk_level", "financial_risk_score", "timeline_risk_score",
    "duplicate_risk_score", "payment_risk_score", "peer_risk_score",
    "raw_max_similarity", "most_similar_work_id",
}

FULL_CANONICAL_ID_RE = re.compile(r"^WS/MP\d+/\d{4}-\d{4}/\d+$")


def main():
    result = build_canonical_dataset()
    write_outputs(result, OUTPUT_DIR)

    c = result.canonical_projects
    q = result.quality_report

    print("=" * 88)
    print("PHASE 2 — CANONICAL DATASET REPORT")
    print("=" * 88)
    print(f"\nTotal canonical Work IDs: {q['total_canonical_work_ids']}")

    print("\n--- Stage presence ---")
    for st, cnt in q["stage_presence_counts"].items():
        print(f"  {st:12s}: {cnt:6d}  ({q['stage_presence_pct'][st]}%)")

    print("\n--- Number of stages present per project (1-4) ---")
    for k, v in q["n_stages_present_distribution"].items():
        print(f"  {k} stage(s): {v}")

    print("\n--- House membership ---")
    for k, v in q["house_membership"].items():
        print(f"  {k}: {v}")

    print("\n--- Missing-field coverage ---")
    for key in ("missing_state", "missing_constituency", "missing_mp",
                "missing_sanction_amount", "missing_sanction_date",
                "missing_completion_date", "missing_expenditure_record"):
        print(f"  {key}: {q[key]}")

    print("\n--- Conflicts ---")
    print(f"  total conflicting field-records: {q['conflicting_field_records']}")
    for field_name, cnt in q["conflicts_by_field"].items():
        print(f"    {field_name}: {cnt}")

    print("\n--- Duplicate canonical Work IDs ---")
    print(f"  {q['duplicate_canonical_work_ids']} (must be 0)")

    print("\n--- Unkeyed Recommended records (no valid Work ID) ---")
    print(f"  total: {q['unkeyed_recommended_records']['total']}")
    print(f"  by house: {q['unkeyed_recommended_records']['by_house']}")

    print("\n--- Expenditure aggregation sanity ---")
    for k, v in q["expenditure_aggregation_sanity"].items():
        print(f"  {k}: {v}")

    print("\n--- Lifecycle sanity-check flags (data-quality signals, NOT fraud) ---")
    for k, v in q["lifecycle_sanity_flags"].items():
        print(f"  {k}: {v}")

    print("\n--- First 5 canonical rows (key columns) ---")
    preview_cols = ["work_id", "houses", "state", "mp", "work_category",
                     "recommended_amount", "sanction_amount", "total_expenditure",
                     "stages_present", "any_field_conflict"]
    preview_cols = [col for col in preview_cols if col in c.columns]
    print(c[preview_cols].head(5).to_string(index=False))

    # --- assertions -------------------------------------------------------
    print("\n" + "=" * 88)
    print("ASSERTIONS")
    print("=" * 88)

    checks = []

    checks.append(("canonical work_id uniqueness", c["work_id"].is_unique))

    no_footer = not c["work_id"].astype(str).str.contains("Grand Total", case=False, na=False).any()
    checks.append(("no footer rows leaked into canonical table", no_footer))

    malformed = ~c["work_id"].astype(str).apply(lambda v: bool(FULL_CANONICAL_ID_RE.match(v)))
    checks.append(("no malformed canonical Work IDs", int(malformed.sum()) == 0))

    no_risk_cols = not (PRECOMPUTED_RISK_COLUMNS & set(c.columns))
    checks.append(("no precomputed risk columns present in canonical_projects", no_risk_cols))

    all_pass = True
    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{status}] {name}")

    print("\n" + "=" * 88)
    print("PHASE 2: " + ("PASS" if all_pass else "FAIL"))
    print("=" * 88)

    print(f"\nOutputs written to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()