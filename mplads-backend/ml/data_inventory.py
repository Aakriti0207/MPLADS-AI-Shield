from pathlib import Path
import pandas as pd

RAW_DIR = Path("data/raw")


def inspect_file(path):
    print("\n" + "=" * 80)
    print(f"FILE: {path.name}")
    print("=" * 80)

    try:
        df = pd.read_csv(path, low_memory=False)

        print(f"Rows       : {len(df):,}")
        print(f"Columns    : {len(df.columns)}")

        print("\nColumns:")
        for col in df.columns:
            print(f"  - {col}")

        print("\nData types:")
        print(df.dtypes.to_string())

        print("\nMissing values:")
        missing = df.isna().sum()
        missing = missing[missing > 0].sort_values(ascending=False)

        if len(missing):
            print(missing.to_string())
        else:
            print("  None")

        print("\nUnique values:")
        for col in df.columns:
            print(f"  {col}: {df[col].nunique(dropna=True):,}")

        print("\nSample:")
        print(df.head(2).to_string(index=False))

    except Exception as e:
        print(f"ERROR reading {path.name}: {e}")


def main():
    files = sorted(RAW_DIR.glob("*.csv"))

    if not files:
        print(f"No CSV files found in {RAW_DIR}")
        return

    print(f"Found {len(files)} CSV files.")

    for file in files:
        inspect_file(file)


if __name__ == "__main__":
    main()