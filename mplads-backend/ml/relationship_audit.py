from pathlib import Path
import pandas as pd
import re

RAW_DIR = Path("data/raw")

FILES = {
    "LS_recommended": "LS_Works Recommended.csv",
    "LS_sanctioned": "LS_Works_Sanctioned__1_.csv",
    "LS_completed": "LS_Works Completed (1).csv",
    "LS_expenditure": "LS_Expenditure on Completed and On-going Works as on Date.csv",
    "RS_recommended": "RS_Works_Recommended.csv",
    "RS_sanctioned": "RS_Works_Sanctioned.csv",
    "RS_completed": "RS_Works_Completed.csv",
    "RS_expenditure": "RS_Expenditure_on_Completed_and_On-going_Works_as_on_Date.csv",
}


def normalize_id(value):
    if pd.isna(value):
        return None

    value = str(value)

    # Remove whitespace and common hidden formatting
    value = re.sub(r"\s+", "", value)
    value = value.upper()

    match = re.search(
        r"WS/MP\d+/\d{4}-\d{4}/\d+",
        value
    )

    return match.group(0) if match else None


def get_ids(df):
    if "Work ID" in df.columns:
        return df["Work ID"].apply(normalize_id)

    for column in ["WORK", "Work"]:
        if column in df.columns:
            return df[column].apply(normalize_id)

    return pd.Series([None] * len(df))


def main():

    data = {}

    print("=" * 80)
    print("BUILDING GLOBAL WORK-ID INDEX")
    print("=" * 80)

    for name, filename in FILES.items():

        path = RAW_DIR / filename
        df = pd.read_csv(path, low_memory=False)

        df["_work_id"] = get_ids(df)

        data[name] = df

        valid = df["_work_id"].dropna()

        print(
            f"{name:20s} "
            f"rows={len(df):6,} "
            f"valid_ids={len(valid):6,} "
            f"unique_ids={valid.nunique():6,}"
        )

    # ---------------------------------------------------------
    # GLOBAL INDEX
    # ---------------------------------------------------------

    global_index = {}

    for dataset_name, df in data.items():

        for work_id in df["_work_id"].dropna().unique():

            if work_id not in global_index:
                global_index[work_id] = []

            global_index[work_id].append(dataset_name)

    print("\n" + "=" * 80)
    print("GLOBAL WORK LIFECYCLE ANALYSIS")
    print("=" * 80)

    distribution = {}

    for work_id, datasets in global_index.items():

        count = len(datasets)

        distribution[count] = distribution.get(count, 0) + 1

    for count in sorted(distribution):

        print(
            f"IDs appearing in {count} dataset(s): "
            f"{distribution[count]:,}"
        )

    # ---------------------------------------------------------
    # EXAMPLES OF MULTI-STAGE WORKS
    # ---------------------------------------------------------

    print("\n" + "=" * 80)
    print("EXAMPLES OF WORK IDs APPEARING ACROSS MULTIPLE DATASETS")
    print("=" * 80)

    shown = 0

    for work_id, datasets in global_index.items():

        if len(datasets) >= 3:

            print(f"\n{work_id}")

            for dataset in datasets:
                print(f"  -> {dataset}")

            shown += 1

            if shown >= 20:
                break

    # ---------------------------------------------------------
    # CROSS-HOUSE MATCHING
    # ---------------------------------------------------------

    print("\n" + "=" * 80)
    print("CROSS LS / RS MATCHING")
    print("=" * 80)

    ls_ids = set()

    rs_ids = set()

    for name, df in data.items():

        ids = set(df["_work_id"].dropna())

        if name.startswith("LS_"):
            ls_ids.update(ids)

        elif name.startswith("RS_"):
            rs_ids.update(ids)

    common = ls_ids & rs_ids

    print(f"Unique LS Work IDs: {len(ls_ids):,}")
    print(f"Unique RS Work IDs: {len(rs_ids):,}")
    print(f"IDs appearing in BOTH: {len(common):,}")

    # ---------------------------------------------------------
    # SAVE GLOBAL INDEX
    # ---------------------------------------------------------

    rows = []

    for work_id, datasets in global_index.items():

        rows.append({
            "work_id": work_id,
            "dataset_count": len(datasets),
            "datasets": "|".join(sorted(datasets))
        })

    result = pd.DataFrame(rows)

    output = Path("data/processed")

    output.mkdir(parents=True, exist_ok=True)

    result.to_csv(
        output / "work_id_global_index.csv",
        index=False
    )

    print("\nSaved:")
    print("data/processed/work_id_global_index.csv")

    print("\n" + "=" * 80)
    print("DONE")
    print("=" * 80)


if __name__ == "__main__":
    main()