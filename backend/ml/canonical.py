"""
Phase 2 — Canonical project dataset builder.

12 raw CSVs -> ml.preprocessing (Phase 1) -> ml.sources adapters ->
per-lifecycle-stage tables (one row per Work ID per stage) -> ONE
canonical project table (one row per Work ID overall).

ML-1:
    Deterministic lifecycle status reconciliation.

ML-2:
    Completion evidence is preserved through the canonical dataset.

ML-3:
    District / geographical hierarchy reconciliation from the MPLADS
    implementing-agency (IDA) field.

Nothing downstream of this module should read the raw CSVs directly --
future feature engineering and detectors consume canonical_projects.csv
(or build_canonical_dataset()'s in-memory result) instead.

Deliberately does not import, reference, or otherwise use
project_risk_scores.csv or any precomputed risk column anywhere in this
file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from ml.preprocessing import preprocess_file
from ml.config import WORK_ID_PATTERN
from ml.status import resolve_status_frame
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


HOUSEKEEPING_COLUMNS = {
    "sr_no",
    "work",
    "work_id",
    "work_id_canonical",
    "work_id_status",
    "house",
    "source_file",
}


# =========================================================================
# 1. Load + adapt one raw file into a standardized frame
# =========================================================================

@dataclass
class LoadedSource:
    source_type: str
    house: str
    filename: str
    frame: pd.DataFrame
    unkeyed: pd.DataFrame
    rows_loaded: int
    footer_rows_dropped: int


def load_and_adapt(source: SourceFile) -> LoadedSource:
    df, report = preprocess_file(resolve_path(source))

    mapping = COLUMN_MAPPINGS[source.source_type]

    rename = {
        src: dst
        for src, dst in mapping.items()
        if src in df.columns
    }

    df = df.rename(columns=rename)

    df["house"] = source.house
    df["source_file"] = source.filename

    if source.source_type in LIFECYCLE_SOURCE_TYPES:

        valid = df[
            df["work_id_status"] == "valid"
        ].copy()

        unkeyed = df[
            df["work_id_status"] != "valid"
        ].copy()

        # The raw 'work_id' column is redundant with
        # 'work_id_canonical' once extraction has happened.
        if "work_id" in valid.columns:
            valid = valid.drop(columns=["work_id"])
            unkeyed = unkeyed.drop(columns=["work_id"])

        valid = valid.rename(
            columns={
                "work_id_canonical": "work_id"
            }
        )

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


def reconcile_values(
    candidates: list[tuple[str, object]]
) -> FieldReconciliation:
    """
    candidates: [(source_label, value), ...] in priority order
    (first entry wins ties).

    Values are assumed already Phase-1-normalized
    (whitespace-collapsed, null-tokened).

    This performs plain equality comparison and does not perform a
    second generic normalization pass.
    """

    def is_present(v) -> bool:
        if v is None:
            return False

        try:
            if pd.isna(v):
                return False
        except (TypeError, ValueError):
            pass

        return str(v).strip() != ""

    non_null = [
        (src, v)
        for src, v in candidates
        if is_present(v)
    ]

    if not non_null:
        return FieldReconciliation(
            None,
            False,
            [],
        )

    distinct = []

    for _, v in non_null:
        if v not in distinct:
            distinct.append(v)

    return FieldReconciliation(
        non_null[0][1],
        len(distinct) > 1,
        distinct,
    )


# =========================================================================
# 2A. ML-3 — District extraction + normalization
# =========================================================================

def extract_district_from_ida(
    value,
) -> Optional[str]:
    """
    Extract the district candidate from an MPLADS IDA string.

    Examples:

        PATNA(DISTRICT PLANNING OFFICER PATNA_IDA)
        -> PATNA

        BILASPUR(DEPUTY COMMISSIONER, BILASPUR)
        -> BILASPUR

        Khargone (West Nimar)(DISTRICT COLLECTOR KHARGONE_IDA)
        -> Khargone (West Nimar)

    The portion before the first '(' is treated as the district
    candidate because MPLADS IDA values encode the district/area
    in this position.

    Returns None for missing/empty values.
    """

    if value is None or pd.isna(value):
        return None

    text = str(value).strip()

    if not text:
        return None

    district = text.split(
        "(",
        1,
    )[0].strip()

    return (
        district
        if district
        else None
    )


def normalize_district_name(
    value,
) -> Optional[str]:
    """
    Conservatively normalize a district candidate extracted from IDA.

    This intentionally avoids fuzzy matching and geographical guessing.

    Only formatting normalization and explicit source-name aliases are
    applied.
    """

    district = extract_district_from_ida(value)

    if district is None:
        return None

    # Normalize repeated whitespace.
    district = " ".join(
        district.split()
    )

    # Explicit aliases observed in the source data.
    #
    # These mappings are deliberately conservative.
    aliases = {
        "Sundaragada": "Sundargarh",
        "Narsimhapur": "Narsinghpur",
        "Darbanga": "Darbhanga",
        "JANJGIR-CHAMPA": "Janjgir-Champa",
        "Janjgir-Champa": "Janjgir-Champa",
        "S.A.S Nagar": "S.A.S. Nagar",
    }

    return aliases.get(
        district,
        district,
    )


def reconcile_districts(
    merged: pd.DataFrame,
    stage_tables: dict[str, pd.DataFrame],
    suffix_map: dict[str, str],
) -> tuple[list, list, list, list]:
    """
    ML-3 district / geographical hierarchy reconciliation.

    District is derived from the implementing_agency (IDA) field.

    The implementation is vectorized over the merged dataframe rather
    than performing a full iterrows() reconciliation pass.

    Returns:

        district_values
        district_conflicts
        district_sources
        district_conflict_records
    """

    district_stage_cols = {
        st: f"implementing_agency{suffix_map[st]}"
        for st in stage_tables
        if f"implementing_agency{suffix_map[st]}"
        in merged.columns
    }

    if not district_stage_cols:
        n = len(merged)

        return (
            [None] * n,
            [False] * n,
            [None] * n,
            [],
        )

    # ---------------------------------------------------------------------
    # Build normalized district candidates for every lifecycle stage.
    # ---------------------------------------------------------------------

    candidate_frames = []

    for stage in STAGE_PRIORITY:

        col = district_stage_cols.get(stage)

        if col is None:
            continue

        candidates = merged[col].map(
            normalize_district_name
        )

        candidate_frames.append(
            pd.Series(
                candidates.values,
                index=merged.index,
                name=stage,
            )
        )

    if not candidate_frames:
        n = len(merged)

        return (
            [None] * n,
            [False] * n,
            [None] * n,
            [],
        )

    district_candidates = pd.concat(
        candidate_frames,
        axis=1,
    )

    # ---------------------------------------------------------------------
    # Determine chosen district.
    #
    # STAGE_PRIORITY determines which stage wins if more than one
    # normalized district candidate exists.
    # ---------------------------------------------------------------------

    district_values = (
        district_candidates
        .bfill(axis=1)
        .iloc[:, 0]
        .tolist()
    )

    # ---------------------------------------------------------------------
    # Determine genuine district conflicts.
    #
    # Different IDA wording for the same normalized district is NOT a
    # conflict.
    # ---------------------------------------------------------------------

    district_conflicts = (
        district_candidates
        .nunique(
            axis=1,
            dropna=True,
        )
        .gt(1)
        .tolist()
    )

    # ---------------------------------------------------------------------
    # Determine which lifecycle stages supplied district information.
    # ---------------------------------------------------------------------

    source_matrix = district_candidates.notna()

    district_sources = []

    for _, row in source_matrix.iterrows():

        sources = [
            stage
            for stage in district_candidates.columns
            if bool(row[stage])
        ]

        district_sources.append(
            ",".join(sources)
            if sources
            else None
        )

    # ---------------------------------------------------------------------
    # Build conflict records only for genuine disagreements.
    # ---------------------------------------------------------------------

    district_conflict_records = []

    conflict_indices = [
        i
        for i, conflict
        in enumerate(district_conflicts)
        if conflict
    ]

    for i in conflict_indices:

        row = district_candidates.iloc[i]

        distinct_values = []

        for value in row.dropna().tolist():
            if value not in distinct_values:
                distinct_values.append(value)

        district_conflict_records.append({
            "work_id": merged.iloc[i]["work_id"],
            "stage": "cross_stage",
            "field": "district",
            "values_found": distinct_values,
            "chosen_value": district_values[i],
            "resolution_reason": (
                "normalized district disagreement across "
                f"lifecycle stages; stage priority "
                f"{STAGE_PRIORITY}"
            ),
        })

    return (
        district_values,
        district_conflicts,
        district_sources,
        district_conflict_records,
    )


# =========================================================================
# 3. Collapse a lifecycle stage's LS+RS rows to one row per Work ID
# =========================================================================

def collapse_stage(
    loaded_sources: list[LoadedSource],
    stage_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Combine a stage's per-house frames and collapse to one row per
    Work ID.

    If a Work ID appears more than once within the combined stage data,
    every shared column is reconciled via reconcile_values().

    Returns:

        collapsed_df
        conflicts_df
    """

    if not loaded_sources:
        return (
            pd.DataFrame(
                columns=[
                    "work_id",
                    "houses",
                ]
            ),
            pd.DataFrame(),
        )

    combined = pd.concat(
        [
            ls.frame
            for ls in loaded_sources
        ],
        ignore_index=True,
    )

    value_columns = [
        c
        for c in combined.columns
        if c not in HOUSEKEEPING_COLUMNS
    ]

    rows = []
    conflicts = []

    for work_id, group in combined.groupby(
        "work_id",
        sort=False,
    ):

        row = {
            "work_id": work_id,
            "houses": ",".join(
                sorted(
                    set(
                        group["house"]
                    )
                )
            ),
        }

        for col in value_columns:

            candidates = list(
                zip(
                    group["house"],
                    group[col],
                )
            )

            result = reconcile_values(
                candidates
            )

            row[col] = result.chosen_value

            if result.conflict:
                conflicts.append({
                    "work_id": work_id,
                    "stage": stage_name,
                    "field": col,
                    "values_found": (
                        result.distinct_values
                    ),
                    "chosen_value": (
                        result.chosen_value
                    ),
                    "resolution_reason": (
                        "first-seen-in-row-order "
                        "(within-stage, no house "
                        "priority defined)"
                    ),
                })

        rows.append(row)

    return (
        pd.DataFrame(rows),
        pd.DataFrame(conflicts),
    )


# =========================================================================
# 4. Expenditure aggregation
# =========================================================================

PAYMENT_SUCCESS_STATUS = "Payment Success"
PAYMENT_IN_PROGRESS_STATUS = "Payment In-Progress"


def aggregate_expenditure(
    loaded_sources: list[LoadedSource],
) -> tuple[pd.DataFrame, pd.DataFrame]:

    if not loaded_sources:
        return (
            pd.DataFrame(
                columns=[
                    "work_id",
                    "houses",
                ]
            ),
            pd.DataFrame(),
        )

    combined = pd.concat(
        [
            ls.frame
            for ls in loaded_sources
        ],
        ignore_index=True,
    )

    identity_cols = [
        c
        for c in (
            "state",
            "implementing_agency",
            "mp",
            "constituency",
            "elected_nominated",
        )
        if c in combined.columns
    ]

    rows = []
    conflicts = []

    for work_id, group in combined.groupby(
        "work_id",
        sort=False,
    ):

        amounts = pd.to_numeric(
            group["fund_disbursed_amount"],
            errors="coerce",
        )

        is_success = (
            group["payment_status"]
            == PAYMENT_SUCCESS_STATUS
        )

        is_in_progress = (
            group["payment_status"]
            == PAYMENT_IN_PROGRESS_STATUS
        )

        dates = pd.to_datetime(
            group["expenditure_date"],
            errors="coerce",
        )

        row = {
            "work_id": work_id,

            "houses": ",".join(
                sorted(
                    set(
                        group["house"]
                    )
                )
            ),

            "total_expenditure": float(
                amounts[
                    is_success
                ].sum()
            ),

            "total_amount_in_progress": float(
                amounts[
                    is_in_progress
                ].sum()
            ),

            "n_expenditure_transactions": int(
                len(group)
            ),

            "n_distinct_vendors": int(
                group[
                    "vendor_name"
                ]
                .dropna()
                .nunique()
            ),

            "n_payment_success": int(
                is_success.sum()
            ),

            "n_payment_in_progress": int(
                is_in_progress.sum()
            ),

            "first_expenditure_date": (
                dates.min().date()
                if dates.notna().any()
                else None
            ),

            "last_expenditure_date": (
                dates.max().date()
                if dates.notna().any()
                else None
            ),
        }

        for col in identity_cols:

            candidates = list(
                zip(
                    group["house"],
                    group[col],
                )
            )

            result = reconcile_values(
                candidates
            )

            row[col] = result.chosen_value

            if result.conflict:
                conflicts.append({
                    "work_id": work_id,
                    "stage": EXPENDITURE,
                    "field": col,
                    "values_found": (
                        result.distinct_values
                    ),
                    "chosen_value": (
                        result.chosen_value
                    ),
                    "resolution_reason": (
                        "first-seen-in-row-order "
                        "across expenditure "
                        "transactions"
                    ),
                })

        rows.append(row)

    return (
        pd.DataFrame(rows),
        pd.DataFrame(conflicts),
    )


# =========================================================================
# 5. Reference tables
# =========================================================================

def build_reference_table(
    source_type: str,
) -> pd.DataFrame:

    loaded = [
        load_and_adapt(s)
        for s in sources_of_type(
            source_type
        )
    ]

    if not loaded:
        return pd.DataFrame()

    frames = []

    for ls in loaded:
        frames.append(
            ls.frame.copy()
        )

    return pd.concat(
        frames,
        ignore_index=True,
    )


# =========================================================================
# 6. Cross-stage merge into canonical project table
# =========================================================================

STAGE_BUILDERS = {
    RECOMMENDED: lambda sources:
        collapse_stage(
            sources,
            RECOMMENDED,
        ),

    SANCTIONED: lambda sources:
        collapse_stage(
            sources,
            SANCTIONED,
        ),

    COMPLETED: lambda sources:
        collapse_stage(
            sources,
            COMPLETED,
        ),
}


def _merge_reconciled_field(
    row: pd.Series,
    field_name: str,
    stage_cols: dict[str, str],
) -> FieldReconciliation:

    candidates = []

    for stage in STAGE_PRIORITY:

        col = stage_cols.get(stage)

        if (
            col is not None
            and col in row.index
        ):
            candidates.append(
                (
                    stage,
                    row[col],
                )
            )

    return reconcile_values(
        candidates
    )


@dataclass
class CanonicalResult:
    canonical_projects: pd.DataFrame
    mp_allocation_reference: pd.DataFrame
    calamity_consent_reference: pd.DataFrame
    canonical_conflicts: pd.DataFrame
    unkeyed_recommended_records: pd.DataFrame
    quality_report: dict = field(
        default_factory=dict
    )


def build_canonical_dataset() -> CanonicalResult:

    all_conflicts = []

    # ---------------------------------------------------------------------
    # Lifecycle stages
    # ---------------------------------------------------------------------

    stage_loaded = {
        st: [
            load_and_adapt(s)
            for s in sources_of_type(st)
        ]
        for st in LIFECYCLE_SOURCE_TYPES
    }

    recommended_tbl, c1 = collapse_stage(
        stage_loaded[RECOMMENDED],
        RECOMMENDED,
    )

    sanctioned_tbl, c2 = collapse_stage(
        stage_loaded[SANCTIONED],
        SANCTIONED,
    )

    completed_tbl, c3 = collapse_stage(
        stage_loaded[COMPLETED],
        COMPLETED,
    )

    expenditure_tbl, c4 = aggregate_expenditure(
        stage_loaded[EXPENDITURE]
    )

    all_conflicts.extend(
        [
            c1,
            c2,
            c3,
            c4,
        ]
    )

    # ---------------------------------------------------------------------
    # Unkeyed recommended records
    # ---------------------------------------------------------------------

    unkeyed_recommended = (
        pd.concat(
            [
                ls.unkeyed
                for ls
                in stage_loaded[RECOMMENDED]
            ],
            ignore_index=True,
        )
        if stage_loaded[RECOMMENDED]
        else pd.DataFrame()
    )

    # ---------------------------------------------------------------------
    # Outer merge four stage tables on Work ID
    # ---------------------------------------------------------------------

    stage_tables = {
        RECOMMENDED: recommended_tbl,
        SANCTIONED: sanctioned_tbl,
        COMPLETED: completed_tbl,
        EXPENDITURE: expenditure_tbl,
    }

    suffix_map = {
        st: f"__{st}"
        for st in stage_tables
    }

    merged = None

    for st, tbl in stage_tables.items():

        renamed = tbl.rename(
            columns={
                c: (
                    f"{c}"
                    f"{suffix_map[st]}"
                )
                for c in tbl.columns
                if c != "work_id"
            }
        )

        if merged is None:
            merged = renamed

        else:
            merged = merged.merge(
                renamed,
                on="work_id",
                how="outer",
            )

    # ---------------------------------------------------------------------
    # Stage-presence flags
    # ---------------------------------------------------------------------

    has_flags = pd.DataFrame({
        "work_id": merged["work_id"]
    })

    for st in stage_tables:

        has_flags[
            f"has_{st}_record"
        ] = merged[
            f"houses__{st}"
        ].notna()

    houses_union = merged[
        [
            c
            for c in merged.columns
            if c.startswith("houses__")
        ]
    ].apply(
        lambda r:
            ",".join(
                sorted(
                    set(
                        h
                        for v in r
                        if pd.notna(v)
                        for h in str(v).split(",")
                    )
                )
            ),
        axis=1,
    )

    # ---------------------------------------------------------------------
    # Reconcile shared identity/attribute fields
    # ---------------------------------------------------------------------

    field_to_stage_cols = {}

    for f_name in RECONCILED_LIFECYCLE_FIELDS:

        field_to_stage_cols[f_name] = {
            st: (
                f"{f_name}"
                f"{suffix_map[st]}"
            )
            for st in stage_tables
            if (
                f"{f_name}"
                f"{suffix_map[st]}"
            ) in merged.columns
        }

    reconciled_cols = {}
    conflict_records = []

    for f_name, stage_cols in field_to_stage_cols.items():

        chosen_list = []
        conflict_list = []

        for _, row in merged.iterrows():

            result = _merge_reconciled_field(
                row,
                f_name,
                stage_cols,
            )

            chosen_list.append(
                result.chosen_value
            )

            conflict_list.append(
                result.conflict
            )

            if result.conflict:
                conflict_records.append({
                    "work_id": row["work_id"],
                    "stage": "cross_stage",
                    "field": f_name,
                    "values_found": (
                        result.distinct_values
                    ),
                    "chosen_value": (
                        result.chosen_value
                    ),
                    "resolution_reason": (
                        f"stage priority "
                        f"{STAGE_PRIORITY}"
                    ),
                })

        reconciled_cols[f_name] = (
            chosen_list
        )

        reconciled_cols[
            f"{f_name}_conflict"
        ] = conflict_list

    # ---------------------------------------------------------------------
    # Create canonical dataframe
    # ---------------------------------------------------------------------

    canonical = pd.DataFrame({
        "work_id": merged["work_id"],
        "houses": houses_union,
    })

    for k, v in reconciled_cols.items():
        canonical[k] = v

    for c in has_flags.columns:

        if c != "work_id":
            canonical[c] = (
                has_flags[c].values
            )

    # ---------------------------------------------------------------------
    # ML-3 — District / geographical hierarchy reconciliation
    # ---------------------------------------------------------------------

    (
        district_values,
        district_conflicts,
        district_sources,
        district_conflict_records,
    ) = reconcile_districts(
        merged,
        stage_tables,
        suffix_map,
    )

    canonical["district"] = (
        district_values
    )

    canonical["district_conflict"] = (
        district_conflicts
    )

    canonical["district_source"] = (
        district_sources
    )

    conflict_records.extend(
        district_conflict_records
    )

    # ---------------------------------------------------------------------
    # Stage-unique fields
    # ---------------------------------------------------------------------

    canonical["recommended_amount"] = (
        merged.get(
            f"recommended_amount"
            f"{suffix_map[RECOMMENDED]}"
        )
    )

    canonical["sanction_amount"] = (
        merged.get(
            f"sanction_amount"
            f"{suffix_map[SANCTIONED]}"
        )
    )

    canonical["work_status"] = (
        merged.get(
            f"work_status"
            f"{suffix_map[SANCTIONED]}"
        )
    )

    canonical["completion_date"] = (
        merged.get(
            f"completion_date"
            f"{suffix_map[COMPLETED]}"
        )
    )

    canonical["amount_disbursed"] = (
        merged.get(
            f"amount_disbursed"
            f"{suffix_map[COMPLETED]}"
        )
    )

    canonical["image"] = (
        merged.get(
            f"image"
            f"{suffix_map[COMPLETED]}"
        )
    )

    for col in (
        "total_expenditure",
        "total_amount_in_progress",
        "n_expenditure_transactions",
        "n_distinct_vendors",
        "n_payment_success",
        "n_payment_in_progress",
        "first_expenditure_date",
        "last_expenditure_date",
    ):

        canonical[col] = merged.get(
            f"{col}"
            f"{suffix_map[EXPENDITURE]}"
        )

    # ---------------------------------------------------------------------
    # ML-1 — Canonical lifecycle status
    # ---------------------------------------------------------------------
    #
    # `work_status` remains the raw, unreconciled Sanctioned-stage text.
    #
    # `status` is the deterministic lifecycle field used by the backend,
    # database and dashboard.
    # ---------------------------------------------------------------------

    canonical["status"] = (
        resolve_status_frame(
            canonical
        )
    )

    # ---------------------------------------------------------------------
    # Lifecycle stage metadata
    # ---------------------------------------------------------------------

    canonical[
        "n_lifecycle_stages_present"
    ] = canonical[
        [
            f"has_{st}_record"
            for st in stage_tables
        ]
    ].sum(axis=1)

    canonical[
        "stages_present"
    ] = canonical[
        [
            f"has_{st}_record"
            for st in stage_tables
        ]
    ].apply(
        lambda r:
            ",".join(
                st
                for st, present
                in zip(
                    stage_tables.keys(),
                    r,
                )
                if present
            ),
        axis=1,
    )

    # ---------------------------------------------------------------------
    # Conflict summary
    # ---------------------------------------------------------------------

    conflict_field_cols = [
        c
        for c in canonical.columns
        if c.endswith("_conflict")
    ]

    canonical[
        "any_field_conflict"
    ] = canonical[
        conflict_field_cols
    ].any(axis=1)

    # ---------------------------------------------------------------------
    # Lifecycle sanity checks
    # ---------------------------------------------------------------------

    rec_date = pd.to_datetime(
        canonical["recommended_date"],
        errors="coerce",
    )

    sanc_date = pd.to_datetime(
        canonical["sanction_date"],
        errors="coerce",
    )

    comp_date = pd.to_datetime(
        canonical["completion_date"],
        errors="coerce",
    )

    first_exp_date = pd.to_datetime(
        canonical["first_expenditure_date"],
        errors="coerce",
    )

    canonical[
        "flag_completion_without_sanction"
    ] = (
        canonical[
            "has_completed_record"
        ]
        & ~canonical[
            "has_sanctioned_record"
        ]
    )

    canonical[
        "flag_expenditure_without_sanction"
    ] = (
        canonical[
            "has_expenditure_record"
        ]
        & ~canonical[
            "has_sanctioned_record"
        ]
    )

    canonical[
        "flag_sanction_without_recommendation"
    ] = (
        canonical[
            "has_sanctioned_record"
        ]
        & ~canonical[
            "has_recommended_record"
        ]
    )

    canonical[
        "flag_completion_before_sanction"
    ] = (
        comp_date.notna()
        & sanc_date.notna()
        & (
            comp_date
            < sanc_date
        )
    )

    canonical[
        "flag_expenditure_before_recommendation"
    ] = (
        first_exp_date.notna()
        & rec_date.notna()
        & (
            first_exp_date
            < rec_date
        )
    )

    canonical[
        "flag_recommendation_after_sanction"
    ] = (
        rec_date.notna()
        & sanc_date.notna()
        & (
            rec_date
            > sanc_date
        )
    )

    # ---------------------------------------------------------------------
    # Canonical conflicts
    # ---------------------------------------------------------------------

    all_conflicts.append(
        pd.DataFrame(
            conflict_records
        )
    )

    canonical_conflicts = (
        pd.concat(
            [
                c
                for c in all_conflicts
                if not c.empty
            ],
            ignore_index=True,
        )
        if any(
            not c.empty
            for c in all_conflicts
        )
        else pd.DataFrame(
            columns=[
                "work_id",
                "stage",
                "field",
                "values_found",
                "chosen_value",
                "resolution_reason",
            ]
        )
    )

    # ---------------------------------------------------------------------
    # Reference tables
    # ---------------------------------------------------------------------

    mp_allocation_reference = (
        build_reference_table(
            ALLOCATED_LIMIT
        )
    )

    calamity_consent_reference = (
        build_reference_table(
            CALAMITY_CONSENT
        )
    )

    # ---------------------------------------------------------------------
    # Result
    # ---------------------------------------------------------------------

    result = CanonicalResult(
        canonical_projects=canonical,
        mp_allocation_reference=(
            mp_allocation_reference
        ),
        calamity_consent_reference=(
            calamity_consent_reference
        ),
        canonical_conflicts=(
            canonical_conflicts
        ),
        unkeyed_recommended_records=(
            unkeyed_recommended
        ),
    )

    result.quality_report = (
        build_quality_report(
            result,
            stage_loaded,
        )
    )

    return result


# =========================================================================
# 7. Quality report
# =========================================================================

def build_quality_report(
    result: CanonicalResult,
    stage_loaded: dict,
) -> dict:

    c = result.canonical_projects
    n = len(c)

    def pct(x):
        return (
            round(
                100 * x / n,
                2,
            )
            if n
            else 0.0
        )

    stage_presence = {
        st: int(
            c[
                f"has_{st}_record"
            ].sum()
        )
        for st in LIFECYCLE_SOURCE_TYPES
    }

    stage_count_dist = (
        c[
            "n_lifecycle_stages_present"
        ]
        .value_counts()
        .sort_index()
        .to_dict()
    )

    house_membership = {
        "LS_only": 0,
        "RS_only": 0,
        "both": 0,
    }

    for houses in c["houses"]:

        parts = (
            set(
                houses.split(",")
            )
            if houses
            else set()
        )

        if parts == {"LS"}:

            house_membership[
                "LS_only"
            ] += 1

        elif parts == {"RS"}:

            house_membership[
                "RS_only"
            ] += 1

        elif len(parts) > 1:

            house_membership[
                "both"
            ] += 1

    report = {

        "total_canonical_work_ids": n,

        "stage_presence_counts": (
            stage_presence
        ),

        "stage_presence_pct": {
            k: pct(v)
            for k, v
            in stage_presence.items()
        },

        "n_stages_present_distribution": {
            str(k): v
            for k, v
            in stage_count_dist.items()
        },

        "house_membership": (
            house_membership
        ),

        # Existing hierarchy
        "missing_state": int(
            c["state"].isna().sum()
        ),

        "missing_constituency": int(
            c[
                "constituency"
            ].isna().sum()
        ),

        "missing_mp": int(
            c["mp"].isna().sum()
        ),

        # ---------------------------------------------------------------
        # ML-3 hierarchy metrics
        # ---------------------------------------------------------------

        "missing_district": int(
            c[
                "district"
            ].isna().sum()
        ),

        "district_conflicts": int(
            c[
                "district_conflict"
            ].sum()
        ),

        "district_sources": (
            c[
                "district_source"
            ]
            .value_counts(
                dropna=False
            )
            .to_dict()
        ),

        # Existing lifecycle/financial metrics
        "missing_sanction_amount": int(
            c[
                "sanction_amount"
            ].isna().sum()
        ),

        "missing_sanction_date": int(
            c[
                "sanction_date"
            ].isna().sum()
        ),

        "missing_completion_date": int(
            c[
                "completion_date"
            ].isna().sum()
        ),

        "missing_expenditure_record": int(
            (
                ~c[
                    "has_expenditure_record"
                ]
            ).sum()
        ),

        "conflicting_field_records": (
            len(
                result.canonical_conflicts
            )
        ),

        "conflicts_by_field": (
            result.canonical_conflicts[
                "field"
            ]
            .value_counts()
            .to_dict()
            if len(
                result.canonical_conflicts
            )
            else {}
        ),

        "duplicate_canonical_work_ids": int(
            c[
                "work_id"
            ].duplicated().sum()
        ),

        "unkeyed_recommended_records": {

            "total": len(
                result
                .unkeyed_recommended_records
            ),

            "by_house": (
                result
                .unkeyed_recommended_records[
                    "house"
                ]
                .value_counts()
                .to_dict()
                if len(
                    result
                    .unkeyed_recommended_records
                )
                else {}
            ),
        },

        "expenditure_aggregation_sanity": {

            "projects_with_expenditure_record": int(
                c[
                    "has_expenditure_record"
                ].sum()
            ),

            "total_expenditure_transactions_aggregated": int(
                c[
                    "n_expenditure_transactions"
                ]
                .fillna(0)
                .sum()
            ),

            "mean_transactions_per_project_with_expenditure": (
                round(
                    float(
                        c.loc[
                            c[
                                "has_expenditure_record"
                            ],
                            "n_expenditure_transactions",
                        ].mean()
                    ),
                    2,
                )
                if c[
                    "has_expenditure_record"
                ].any()
                else None
            ),

            "max_transactions_single_project": (
                int(
                    c[
                        "n_expenditure_transactions"
                    ].max()
                )
                if c[
                    "n_expenditure_transactions"
                ].notna().any()
                else None
            ),
        },

        # ML-1 status distribution
        "status_counts": (
            c[
                "status"
            ]
            .value_counts()
            .to_dict()
        ),

        # Lifecycle sanity flags
        "lifecycle_sanity_flags": {

            "completion_without_sanction": int(
                c[
                    "flag_completion_without_sanction"
                ].sum()
            ),

            "expenditure_without_sanction": int(
                c[
                    "flag_expenditure_without_sanction"
                ].sum()
            ),

            "sanction_without_recommendation": int(
                c[
                    "flag_sanction_without_recommendation"
                ].sum()
            ),

            "completion_before_sanction": int(
                c[
                    "flag_completion_before_sanction"
                ].sum()
            ),

            "expenditure_before_recommendation": int(
                c[
                    "flag_expenditure_before_recommendation"
                ].sum()
            ),

            "recommendation_after_sanction": int(
                c[
                    "flag_recommendation_after_sanction"
                ].sum()
            ),
        },
    }

    return report


# =========================================================================
# 8. Output writer
# =========================================================================

def write_outputs(
    result: CanonicalResult,
    output_dir,
) -> None:

    """
    Write the Phase 2 output files to output_dir.

    Never touches data/raw/.

    Writes only under data/processed/.
    """

    import json
    from pathlib import Path

    output_dir = Path(
        output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.canonical_projects.to_csv(
        output_dir
        / "canonical_projects.csv",
        index=False,
    )

    result.mp_allocation_reference.to_csv(
        output_dir
        / "mp_allocation_reference.csv",
        index=False,
    )

    result.calamity_consent_reference.to_csv(
        output_dir
        / "calamity_consent_reference.csv",
        index=False,
    )

    result.canonical_conflicts.to_csv(
        output_dir
        / "canonical_conflicts.csv",
        index=False,
    )

    with open(
        output_dir
        / "canonical_data_quality_report.json",
        "w",
    ) as f:

        json.dump(
            result.quality_report,
            f,
            indent=2,
            default=str,
        )