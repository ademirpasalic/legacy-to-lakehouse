"""Step 0: see what Parquet and Delta Lake actually give you over CSV.

Run after generate_legacy_data.py:
    python scripts/explore_formats.py
"""

import os
import shutil
from pathlib import Path

import pandas as pd
from deltalake import DeltaTable, write_deltalake

DATA = Path(__file__).resolve().parent.parent / "data"
CSV_PATH = DATA / "legacy" / "prod_051_shots_sheets.csv"
PARQUET_PATH = DATA / "scratch" / "shots.parquet"
DELTA_PATH = DATA / "scratch" / "shots_delta"


def main():
    PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(CSV_PATH)

    # Parquet has a fixed metadata overhead, so on a tiny file it can lose to CSV
    df.to_parquet(PARQUET_PATH)
    print(f"Small  CSV: {os.path.getsize(CSV_PATH):>9} bytes")
    print(f"Small  Parquet: {os.path.getsize(PARQUET_PATH):>5} bytes")

    # ...but at realistic sizes the compression wins
    big = pd.concat([df] * 2000, ignore_index=True)
    big_csv, big_parquet = DATA / "scratch" / "big.csv", DATA / "scratch" / "big.parquet"
    big.to_csv(big_csv, index=False)
    big.to_parquet(big_parquet)
    print(f"Big    CSV: {os.path.getsize(big_csv):>9} bytes  ({len(big)} rows)")
    print(f"Big    Parquet: {os.path.getsize(big_parquet):>5} bytes")

    # Parquet only remembers types you actually set; it doesn't guess them
    df["Due date"] = pd.to_datetime(df["Due date"])
    df.to_parquet(PARQUET_PATH)
    print("\nTypes Parquet remembers (after parsing the dates):")
    print(pd.read_parquet(PARQUET_PATH).dtypes)
    print("\nOnly two columns:")
    print(pd.read_parquet(PARQUET_PATH, columns=["Shot", "Task status"]).head())

    # Delta: Parquet files + a log of every change
    shutil.rmtree(DELTA_PATH, ignore_errors=True)
    write_deltalake(DELTA_PATH, df)
    write_deltalake(DELTA_PATH, df.head(10), mode="overwrite")
    table = DeltaTable(DELTA_PATH)
    print(f"\nDelta table now has {len(table.to_pandas())} rows (version {table.version()})")
    print("History:")
    for entry in table.history():
        print(f"  version {entry.get('version')}: {entry.get('operation')}")

    # Time travel: read the table as it was before the overwrite
    old = DeltaTable(DELTA_PATH, version=0).to_pandas()
    print(f"Version 0 had {len(old)} rows")


if __name__ == "__main__":
    main()
