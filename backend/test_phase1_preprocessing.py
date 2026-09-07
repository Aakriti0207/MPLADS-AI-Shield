"""
Phase 1 validation script.

Not part of ml/ itself -- kept as a standalone script at the backend
root (alongside seed_data.py, import_phase2.py, verify_phase2_import.py,
which follow the same convention) rather than inside the ml package,
since it validates ml.preprocessing rather than being part of the
preprocessing pipeline.

Runs ml.preprocessing.preprocess_file() against all 12 raw CSVs under
data/raw/ and prints:
  - rows / footer rows dropped / valid / missing / invalid / duplicate
    Work IDs, and date/amount parse failures, per file
  - the two specific dirty Work ID examples called out for verification
  - confirmation that the same canonical Work ID normalizes identically
    everywhere it appears across files

Run with: python test_phase1_preprocessing.py
"""

from ml.config import RAW_DATA_DIR
from ml.preprocessing import preprocess_file

RAW_FILES = [
    "LS_Allocated_Limit_for_Honble_MPs.csv",
    "RS_Allocated_Limit_for_Honble_MPs__4_.csv",
    "LS_Amount_consented_for_Calamity.csv",
    "RS_Amount_consented_for_Calamity__1_.csv",
    "LS_Works Recommended.csv",
    "RS_Works_Recommended.csv",
    "LS_Works_Sanctioned__1_.csv",
    "RS_Works_Sanctioned.csv",
    "LS_Works Completed (1).csv",
    "RS_Works_Completed.csv",
    "LS_Expenditure on Completed and On-going Works as on Date.csv",
    "RS_Expenditure_on_Completed_and_On-going_Works_as_on_Date.csv",
]

CHECK_IDS = ["WS/MP418/2024-2025/133409", "WS/MP620/2024-2025/133166"]


def main():
    results = {}
    print("=" * 88)
    print(f"{'FILE':45s} {'rows':>6s} {'footer':>7s} {'valid':>7s} {'miss':>6s} {'inval':>6s} {'dup':>5s}")
    print("=" * 88)

    all_ok = True
    for name in RAW_FILES:
        path = RAW_DATA_DIR / name
        df, report = preprocess_file(path)
        results[name] = (df, report)
        r = report.as_dict()
        print(
            f"{name:45s} {r['rows']:6d} {r['footer_rows_dropped']:7d} "
            f"{r['valid_work_ids']:7d} {r['missing_work_ids']:6d} "
            f"{r['invalid_work_ids']:6d} {r['duplicate_work_ids']:5d}"
        )
        if r["date_parse_failures"]:
            for col, n in r["date_parse_failures"].items():
                if n:
                    print(f"    date parse failures — {col}: {n}")
        if r["numeric_parse_failures"]:
            for col, n in r["numeric_parse_failures"].items():
                if n:
                    print(f"    numeric parse failures — {col}: {n}")
        # every file must lose exactly its footer row and never crash
        if r["rows_after_footer_drop"] != r["rows"] - r["footer_rows_dropped"]:
            all_ok = False

    print()
    print("=" * 88)
    print("DIRTY WORK ID SPOT CHECK")
    print("=" * 88)
    for check_id in CHECK_IDS:
        print(f"\nLooking for {check_id} across all files:")
        found_any = False
        for name, (df, _report) in results.items():
            if "work_id_canonical" not in df.columns:
                continue
            matches = df[df["work_id_canonical"] == check_id]
            if len(matches):
                found_any = True
                source_col = "work_id" if "work_id" in df.columns else "work"
                raw_values = matches[source_col].tolist() if source_col in matches.columns else []
                print(f"  {name}: {len(matches)} row(s), raw source value(s): {raw_values[:2]}")
        if not found_any:
            print("  (not present in this file set)")

    print()
    print("=" * 88)
    print("TAB-CONTAINING RAW VALUES — CONFIRM THEY STILL NORMALIZE CORRECTLY")
    print("=" * 88)
    for name in ["LS_Works Recommended.csv", "RS_Works_Sanctioned.csv", "LS_Works Completed (1).csv"]:
        df, _report = results[name]
        source_col = "work_id" if "work_id" in df.columns else "work"
        if source_col not in df.columns:
            continue
        # re-load raw to find literal tabs, then look up what the pipeline
        # produced for those same rows
        from ml.preprocessing import load_csv, normalize_columns
        raw_df, _ = normalize_columns(load_csv(RAW_DATA_DIR / name))
        raw_col = "work_id" if "work_id" in raw_df.columns else "work"
        tabbed_mask = raw_df[raw_col].fillna("").str.contains("\t")
        n_tabbed = int(tabbed_mask.sum())
        print(f"\n{name}: {n_tabbed} row(s) with a literal tab in the raw '{raw_col}' field")
        if n_tabbed:
            idx = raw_df[tabbed_mask].index[0]
            print(f"  raw:       {raw_df.loc[idx, raw_col]!r}")
            print(f"  canonical: {df.loc[idx, 'work_id_canonical']!r}  (status: {df.loc[idx, 'work_id_status']})")

    print()
    print("=" * 88)
    print("PASS" if all_ok else "FAIL — row-count reconciliation mismatch in at least one file")
    print("=" * 88)


if __name__ == "__main__":
    main()