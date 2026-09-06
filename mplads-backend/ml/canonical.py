"""
Phase 2 — Canonical project dataset builder.

12 raw CSVs -> ml.preprocessing (Phase 1) -> ml.sources adapters ->
per-lifecycle-stage tables (one row per Work ID per stage) -> ONE
canonical project table (one row per Work ID overall).

Nothing downstream of this module should read the raw CSVs directly --
future feature engineering and detectors consume canonical_projects.csv
(or build_canonical_dataset()'s in-memory result) instead.

Deliberately does not import, reference, or otherwise use
project_risk_scores.csv or any precomputed risk column anywhere in this
file (grep-verified in the Phase 2 report).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from ml.preprocessing import preprocess_file
from ml.config import WORK_ID_PATTERN
from ml.sources import (
    ALLOCATED_LIMIT,
    CALAMITY_CONSENT,
    COLUMN_MAPPINGS,
    COMPLETED,
    EXPENDITURE,
    LIFECYCLE_SOURCE_TYPES,
    RECOMMENDED,
    RECONCILED_LIFECYCLE_FIELDS,
    SANCTIONED,
    STAGE_PRIORITY,
    SourceFile,
    resolve_path,
    sources_of_type,
)

HOUSEKEEPING_COLUMNS = {"sr_no", "work", "work_id", "work_id_canonical", "work_id_status", "house", "source_file"}


# =========================================================================
# 1. Load + adapt one raw file into a standardized frame
# =========================================================================

@dataclass
class LoadedSource:
    source_type: str
    house: str
    filename: str
    frame: pd.DataFrame       # standardized canonical-ish columns; valid work_id rows only for lifecycle types
    unkeyed: pd.DataFrame     # rows with missing/invalid work_id (lifecycle types only)
    rows_loaded: int
    footer_rows_dropped: int


def load_and_adapt(source: SourceFile) -> LoadedSource:
    df, report = preprocess_file(resolve_path(source))
    mapping = COLUMN_MAPPINGS[source.source_type]
    rename = {src: dst for src, dst in mapping.items() if src in df.columns}
    df = df.rename(columns=rename)
    df["house"] = source.house
    df["source_file"] = source.filename

    if source.source_type in LIFECYCLE_SOURCE_TYPES:
        valid = df[df["work_id_status"] == "valid"].copy()
        unkeyed = df[df["work_id_status"] != "valid"].copy()
        # The raw 'work_id' column (Expenditure files' dedicated column,
        # already the source extract_work_ids() read from) is redundant
        # with 'work_id_canonical' once extraction has happened, and
        # keeping both would create two same-named columns after the
        # rename below.
        if "work_id" in valid.columns:
            valid = valid.drop(columns=["work_id"])
            unkeyed = unkeyed.drop(columns=["work_id"])
        valid = valid.rename(columns={"work_id_canonical": "work_id"})
    else:
        valid = df.copy()
        unkeyed = df.iloc[0:0].copy()

    return LoadedSource(
        source_type=source.source_type,
        house=source.house,
        filename=source.filename,
        frame=valid,
        unkeyed=unkeyed,
        rows_loaded=report.rows_loaded,
        footer_rows_dropped=report.footer_rows_dropped,
    )


# =========================================================================
# 2. Generic value reconciliation
# =========================================================================

@dataclass
class FieldReconciliation:
    chosen_value: object
    conflict: bool
    distinct_values: list


def reconcile_values(candidates: list[tuple[str, object]]) -> FieldReconciliation:
    """candidates: [(source_label, value), ...] in priority order (first
    entry wins ties). Values are assumed already Phase-1-normalized
    (whitespace-collapsed, null-tokened) -- this does a plain equality
    comparison, not a second normalization pass.

    A candidate is "present" only if it's non-null AND non-empty after
    stripping. pd.isna() is used rather than `v is None`, because values
    pulled from an outer-joined DataFrame (a stage that has no row at all
    for this work_id) arrive as float('nan'), not None -- `v is not None`
    alone would treat every absent stage as if it contributed the literal
    text "nan" as a real, distinct value, which would flag a conflict on
    nearly every row regardless of whether the stages that actually have
    data agree. Caught this exact way: initial run showed the 'state' and
    'mp' fields "conflicting" on ~99% of all 43,863 projects, which
    directly contradicted spot checks showing several real projects with
    identical state/mp text across all their stages.
    """
    def is_present(v) -> bool:
        if v is None:
            return False
        try:
            if pd.isna(v):
                return False
        except (TypeError, ValueError):
            pass  # pd.isna() can't evaluate some types (e.g. certain objects); treat as present
        return str(v).strip() != ""

    non_null = [(src, v) for src, v in candidates if is_present(v)]
    if not non_null:
        return FieldReconciliation(None, False, [])
    distinct = []
    for _, v in non_null:
        if v not in distinct:
            distinct.append(v)
    return FieldReconciliation(non_null[0][1], len(distinct) > 1, distinct)


# =========================================================================
# 3. Collapse a lifecycle stage's LS+RS rows to one row per Work ID
# =========================================================================

def collapse_stage(loaded_sources: list[LoadedSource], stage_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Combine a stage's per-house frames and collapse to one row per Work
    ID. If a Work ID appears more than once within the combined stage data
    (whether a genuine LS+RS overlap or a duplicate within one house's
    file), every shared column is reconciled via reconcile_values() using
    row order as the priority (first-seen wins on ties) -- there is no
    stage-priority concept *within* one stage, only across stages.

    Returns (collapsed_df, conflicts_df). collapsed_df carries one extra
    housekeeping column, 'houses', a sorted comma-joined string of every
    house that contributed a row for that Work ID (used for the LS-only /
    RS-only / both report).
    """
    if not loaded_sources:
        return pd.DataFrame(columns=["work_id", "houses"]), pd.DataFrame()

    combined = pd.concat([ls.frame for ls in loaded_sources], ignore_index=True)
    value_columns = [c for c in combined.columns if c not in HOUSEKEEPING_COLUMNS]

    rows = []
    conflicts = []
    for work_id, group in combined.groupby("work_id", sort=False):
        row = {"work_id": work_id, "houses": ",".join(sorted(set(group["house"])))}
        for col in value_columns:
            candidates = list(zip(group["house"], group[col]))
            result = reconcile_values(candidates)
            row[col] = result.chosen_value
            if result.conflict:
                conflicts.append({
                    "work_id": work_id,
                    "stage": stage_name,
                    "field": col,
                    "values_found": result.distinct_values,
                    "chosen_value": result.chosen_value,
                    "resolution_reason": "first-seen-in-row-order (within-stage, no house priority defined)",
                })
        rows.append(row)

    return pd.DataFrame(rows), pd.DataFrame(conflicts)


# =========================================================================
# 4. Expenditure aggregation (many transaction rows -> one row per Work ID)
# =========================================================================

# Confirmed on the actual data: only two real payment_status values occur
# ("Payment Success", "Payment In-Progress") once the Grand-Total footer
# row is dropped. total_expenditure counts Payment Success amounts only --
# an in-progress payment is not yet a completed disbursement, so counting
# it as spend would overstate actual utilization. total_amount_in_progress
# is kept as a separate, clearly-labeled informational figure rather than
# folded into total_expenditure.
PAYMENT_SUCCESS_STATUS = "Payment Success"
PAYMENT_IN_PROGRESS_STATUS = "Payment In-Progress"


def aggregate_expenditure(loaded_sources: list[LoadedSource]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not loaded_sources:
        return pd.DataFrame(columns=["work_id", "houses"]), pd.DataFrame()

    combined = pd.concat([ls.frame for ls in loaded_sources], ignore_index=True)
    identity_cols = [c for c in ("state", "implementing_agency", "mp", "constituency", "elected_nominated")
                      if c in combined.columns]

    rows = []
    conflicts = []
    for work_id, group in combined.groupby("work_id", sort=False):
        amounts = pd.to_numeric(group["fund_disbursed_amount"], errors="coerce")
        is_success = group["payment_status"] == PAYMENT_SUCCESS_STATUS
        is_in_progress = group["payment_status"] == PAYMENT_IN_PROGRESS_STATUS
        dates = pd.to_datetime(group["expenditure_date"], errors="coerce")

        row = {
            "work_id": work_id,
            "houses": ",".join(sorted(set(group["house"]))),
            "total_expenditure": float(amounts[is_success].sum()),
            "total_amount_in_progress": float(amounts[is_in_progress].sum()),
            "n_expenditure_transactions": int(len(group)),
            "n_distinct_vendors": int(group["vendor_name"].dropna().nunique()),
            "n_payment_success": int(is_success.sum()),
            "n_payment_in_progress": int(is_in_progress.sum()),
            "first_expenditure_date": dates.min().date() if dates.notna().any() else None,
            "last_expenditure_date": dates.max().date() if dates.notna().any() else None,
        }
        for col in identity_cols:
            candidates = list(zip(group["house"], group[col]))
            result = reconcile_values(candidates)
            row[col] = result.chosen_value
            if result.conflict:
                conflicts.append({
                    "work_id": work_id,
                    "stage": EXPENDITURE,
                    "field": col,
                    "values_found": result.distinct_values,
                    "chosen_value": result.chosen_value,
                    "resolution_reason": "first-seen-in-row-order across expenditure transactions",
                })
        rows.append(row)

    return pd.DataFrame(rows), pd.DataFrame(conflicts)


# =========================================================================
# 5. Reference tables (not project-level; joined by MP name later, not merged in now)
# =========================================================================

def build_reference_table(source_type: str) -> pd.DataFrame:
    loaded = [load_and_adapt(s) for s in sources_of_type(source_type)]
    if not loaded:
        return pd.DataFrame()
    frames = []
    for ls in loaded:
        f = ls.frame.copy()
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


# =========================================================================
# 6. Cross-stage merge into the canonical project table
# =========================================================================

STAGE_BUILDERS = {
    RECOMMENDED: lambda sources: collapse_stage(sources, RECOMMENDED),
    SANCTIONED: lambda sources: collapse_stage(sources, SANCTIONED),
    COMPLETED: lambda sources: collapse_stage(sources, COMPLETED),
}


def _merge_reconciled_field(row: pd.Series, field_name: str, stage_cols: dict[str, str]) -> FieldReconciliation:
    candidates = []
    for stage in STAGE_PRIORITY:
        col = stage_cols.get(stage)
        if col is not None and col in row.index:
            candidates.append((stage, row[col]))
    return reconcile_values(candidates)


@dataclass
class CanonicalResult:
    canonical_projects: pd.DataFrame
    mp_allocation_reference: pd.DataFrame
    calamity_consent_reference: pd.DataFrame
    canonical_conflicts: pd.DataFrame
    unkeyed_recommended_records: pd.DataFrame
    quality_report: dict = field(default_factory=dict)


def build_canonical_dataset() -> CanonicalResult:
    all_conflicts = []

    # --- lifecycle stages -------------------------------------------------
    stage_loaded = {st: [load_and_adapt(s) for s in sources_of_type(st)] for st in LIFECYCLE_SOURCE_TYPES}

    recommended_tbl, c1 = collapse_stage(stage_loaded[RECOMMENDED], RECOMMENDED)
    sanctioned_tbl, c2 = collapse_stage(stage_loaded[SANCTIONED], SANCTIONED)
    completed_tbl, c3 = collapse_stage(stage_loaded[COMPLETED], COMPLETED)
    expenditure_tbl, c4 = aggregate_expenditure(stage_loaded[EXPENDITURE])
    all_conflicts.extend([c1, c2, c3, c4])

    unkeyed_recommended = pd.concat(
        [ls.unkeyed for ls in stage_loaded[RECOMMENDED]], ignore_index=True
    ) if stage_loaded[RECOMMENDED] else pd.DataFrame()

    # --- outer-merge the four stage tables on work_id ----------------------
    stage_tables = {
        RECOMMENDED: recommended_tbl,
        SANCTIONED: sanctioned_tbl,
        COMPLETED: completed_tbl,
        EXPENDITURE: expenditure_tbl,
    }
    suffix_map = {st: f"__{st}" for st in stage_tables}

    merged = None
    for st, tbl in stage_tables.items():
        renamed = tbl.rename(columns={c: f"{c}{suffix_map[st]}" for c in tbl.columns if c != "work_id"})
        merged = renamed if merged is None else merged.merge(renamed, on="work_id", how="outer")

    has_flags = pd.DataFrame({"work_id": merged["work_id"]})
    for st in stage_tables:
        has_flags[f"has_{st}_record"] = merged[f"houses__{st}"].notna()

    houses_union = merged[[c for c in merged.columns if c.startswith("houses__")]].apply(
        lambda r: ",".join(sorted(set(h for v in r if pd.notna(v) for h in v.split(",")))), axis=1
    )

    # --- reconcile shared identity/attribute fields across stages ---------
    field_to_stage_cols = {}
    for f_name in RECONCILED_LIFECYCLE_FIELDS:
        field_to_stage_cols[f_name] = {
            st: f"{f_name}{suffix_map[st]}"
            for st in stage_tables
            if f"{f_name}{suffix_map[st]}" in merged.columns
        }

    reconciled_cols = {}
    conflict_records = []
    for f_name, stage_cols in field_to_stage_cols.items():
        chosen_list = []
        conflict_list = []
        for _, row in merged.iterrows():
            result = _merge_reconciled_field(row, f_name, stage_cols)
            chosen_list.append(result.chosen_value)
            conflict_list.append(result.conflict)
            if result.conflict:
                conflict_records.append({
                    "work_id": row["work_id"],
                    "stage": "cross_stage",
                    "field": f_name,
                    "values_found": result.distinct_values,
                    "chosen_value": result.chosen_value,
                    "resolution_reason": f"stage priority {STAGE_PRIORITY}",
                })
        reconciled_cols[f_name] = chosen_list
        reconciled_cols[f"{f_name}_conflict"] = conflict_list

    canonical = pd.DataFrame({"work_id": merged["work_id"], "houses": houses_union})
    for k, v in reconciled_cols.items():
        canonical[k] = v
    for c in has_flags.columns:
        if c != "work_id":
            canonical[c] = has_flags[c].values

    # stage-unique fields (not reconciled, single authoritative source)
    canonical["recommended_amount"] = merged.get(f"recommended_amount{suffix_map[RECOMMENDED]}")
    canonical["sanction_amount"] = merged.get(f"sanction_amount{suffix_map[SANCTIONED]}")
    canonical["work_status"] = merged.get(f"work_status{suffix_map[SANCTIONED]}")
    canonical["completion_date"] = merged.get(f"completion_date{suffix_map[COMPLETED]}")
    canonical["amount_disbursed"] = merged.get(f"amount_disbursed{suffix_map[COMPLETED]}")
    canonical["image"] = merged.get(f"image{suffix_map[COMPLETED]}")
    for col in ("total_expenditure", "total_amount_in_progress", "n_expenditure_transactions",
                "n_distinct_vendors", "n_payment_success", "n_payment_in_progress",
                "first_expenditure_date", "last_expenditure_date"):
        canonical[col] = merged.get(f"{col}{suffix_map[EXPENDITURE]}")

    canonical["n_lifecycle_stages_present"] = canonical[[f"has_{st}_record" for st in stage_tables]].sum(axis=1)
    canonical["stages_present"] = canonical[[f"has_{st}_record" for st in stage_tables]].apply(
        lambda r: ",".join(st for st, present in zip(stage_tables.keys(), r) if present), axis=1
    )

    conflict_field_cols = [c for c in canonical.columns if c.endswith("_conflict")]
    canonical["any_field_conflict"] = canonical[conflict_field_cols].any(axis=1)

    # --- lifecycle sanity checks (data-quality signals, not fraud) --------
    rec_date = pd.to_datetime(canonical["recommended_date"], errors="coerce")
    sanc_date = pd.to_datetime(canonical["sanction_date"], errors="coerce")
    comp_date = pd.to_datetime(canonical["completion_date"], errors="coerce")
    first_exp_date = pd.to_datetime(canonical["first_expenditure_date"], errors="coerce")

    canonical["flag_completion_without_sanction"] = canonical["has_completed_record"] & ~canonical["has_sanctioned_record"]
    canonical["flag_expenditure_without_sanction"] = canonical["has_expenditure_record"] & ~canonical["has_sanctioned_record"]
    canonical["flag_sanction_without_recommendation"] = canonical["has_sanctioned_record"] & ~canonical["has_recommended_record"]
    canonical["flag_completion_before_sanction"] = (comp_date.notna() & sanc_date.notna()) & (comp_date < sanc_date)
    canonical["flag_expenditure_before_recommendation"] = (first_exp_date.notna() & rec_date.notna()) & (first_exp_date < rec_date)
    canonical["flag_recommendation_after_sanction"] = (rec_date.notna() & sanc_date.notna()) & (rec_date > sanc_date)

    all_conflicts.append(pd.DataFrame(conflict_records))
    canonical_conflicts = pd.concat([c for c in all_conflicts if not c.empty], ignore_index=True) if any(
        not c.empty for c in all_conflicts
    ) else pd.DataFrame(columns=["work_id", "stage", "field", "values_found", "chosen_value", "resolution_reason"])

    # --- reference tables (not merged into project rows) -------------------
    mp_allocation_reference = build_reference_table(ALLOCATED_LIMIT)
    calamity_consent_reference = build_reference_table(CALAMITY_CONSENT)

    result = CanonicalResult(
        canonical_projects=canonical,
        mp_allocation_reference=mp_allocation_reference,
        calamity_consent_reference=calamity_consent_reference,
        canonical_conflicts=canonical_conflicts,
        unkeyed_recommended_records=unkeyed_recommended,
    )
    result.quality_report = build_quality_report(result, stage_loaded)
    return result


# =========================================================================
# 7. Quality report
# =========================================================================

def build_quality_report(result: CanonicalResult, stage_loaded: dict) -> dict:
    c = result.canonical_projects
    n = len(c)

    def pct(x):
        return round(100 * x / n, 2) if n else 0.0

    stage_presence = {
        st: int(c[f"has_{st}_record"].sum()) for st in LIFECYCLE_SOURCE_TYPES
    }
    stage_count_dist = c["n_lifecycle_stages_present"].value_counts().sort_index().to_dict()

    house_membership = {"LS_only": 0, "RS_only": 0, "both": 0}
    for houses in c["houses"]:
        parts = set(houses.split(",")) if houses else set()
        if parts == {"LS"}:
            house_membership["LS_only"] += 1
        elif parts == {"RS"}:
            house_membership["RS_only"] += 1
        elif len(parts) > 1:
            house_membership["both"] += 1

    report = {
        "total_canonical_work_ids": n,
        "stage_presence_counts": stage_presence,
        "stage_presence_pct": {k: pct(v) for k, v in stage_presence.items()},
        "n_stages_present_distribution": {str(k): v for k, v in stage_count_dist.items()},
        "house_membership": house_membership,
        "missing_state": int(c["state"].isna().sum()),
        "missing_constituency": int(c["constituency"].isna().sum()),
        "missing_mp": int(c["mp"].isna().sum()),
        "missing_sanction_amount": int(c["sanction_amount"].isna().sum()),
        "missing_sanction_date": int(c["sanction_date"].isna().sum()),
        "missing_completion_date": int(c["completion_date"].isna().sum()),
        "missing_expenditure_record": int((~c["has_expenditure_record"]).sum()),
        "conflicting_field_records": len(result.canonical_conflicts),
        "conflicts_by_field": (
            result.canonical_conflicts["field"].value_counts().to_dict()
            if len(result.canonical_conflicts) else {}
        ),
        "duplicate_canonical_work_ids": int(c["work_id"].duplicated().sum()),
        "unkeyed_recommended_records": {
            "total": len(result.unkeyed_recommended_records),
            "by_house": (
                result.unkeyed_recommended_records["house"].value_counts().to_dict()
                if len(result.unkeyed_recommended_records) else {}
            ),
        },
        "expenditure_aggregation_sanity": {
            "projects_with_expenditure_record": int(c["has_expenditure_record"].sum()),
            "total_expenditure_transactions_aggregated": int(c["n_expenditure_transactions"].fillna(0).sum()),
            "mean_transactions_per_project_with_expenditure": (
                round(float(c.loc[c["has_expenditure_record"], "n_expenditure_transactions"].mean()), 2)
                if c["has_expenditure_record"].any() else None
            ),
            "max_transactions_single_project": (
                int(c["n_expenditure_transactions"].max()) if c["n_expenditure_transactions"].notna().any() else None
            ),
        },
        "lifecycle_sanity_flags": {
            "completion_without_sanction": int(c["flag_completion_without_sanction"].sum()),
            "expenditure_without_sanction": int(c["flag_expenditure_without_sanction"].sum()),
            "sanction_without_recommendation": int(c["flag_sanction_without_recommendation"].sum()),
            "completion_before_sanction": int(c["flag_completion_before_sanction"].sum()),
            "expenditure_before_recommendation": int(c["flag_expenditure_before_recommendation"].sum()),
            "recommendation_after_sanction": int(c["flag_recommendation_after_sanction"].sum()),
        },
    }
    return report


# =========================================================================
# 8. Output writer
# =========================================================================

def write_outputs(result: CanonicalResult, output_dir) -> None:
    """Write the five Phase 2 output files to output_dir (created if
    needed). Never touches data/raw/ -- this is the only function in the
    package that writes anything to disk, and it writes only under
    data/processed/.
    """
    import json
    from pathlib import Path

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result.canonical_projects.to_csv(output_dir / "canonical_projects.csv", index=False)
    result.mp_allocation_reference.to_csv(output_dir / "mp_allocation_reference.csv", index=False)
    result.calamity_consent_reference.to_csv(output_dir / "calamity_consent_reference.csv", index=False)
    result.canonical_conflicts.to_csv(output_dir / "canonical_conflicts.csv", index=False)
    with open(output_dir / "canonical_data_quality_report.json", "w") as f:
        json.dump(result.quality_report, f, indent=2, default=str)