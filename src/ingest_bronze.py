"""Bronze: land the legacy exports as-is, plus where and when they came from.

Every file in data/legacy/ becomes one Delta table in data/bronze/<production>.
Values are kept exactly as they were (all read as text), so we can always go
back and check what the legacy system really said. Cleaning happens in silver.

Usage:
    python -m src.ingest_bronze
"""

import json
import sys
from pathlib import Path

import pandas as pd
from deltalake import write_deltalake

ROOT = Path(__file__).resolve().parent.parent
LEGACY_DIR = ROOT / "data" / "legacy"
BRONZE_DIR = ROOT / "data" / "bronze"


def read_legacy_file(path: Path) -> pd.DataFrame:
    """Read a CSV or JSON export with every value as text."""
    if path.suffix == ".csv":
        return pd.read_csv(path, dtype="string", keep_default_na=False)
    if path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            records = json.load(f)
        # Coda nests the owner ({"owner": {"name": ...}}) and mixes 120 and "120 fr"
        # in one column. Flatten it and store everything as text, like the CSVs.
        df = pd.json_normalize(records)
        return df.astype("string").fillna("")
    raise ValueError(f"Unsupported file type: {path.name}")


def production_from_filename(path: Path) -> str:
    """prod_039_shots_excel.csv -> prod_039"""
    return "_".join(path.stem.split("_")[:2])


def ingest(legacy_dir: Path = LEGACY_DIR, bronze_dir: Path = BRONZE_DIR) -> list[str]:
    """Land every legacy file in bronze. Returns the files that failed."""
    ingested_at = pd.Timestamp.now(tz="UTC").floor("us")
    failed = []

    for path in sorted(legacy_dir.glob("*")):
        if path.suffix not in (".csv", ".json"):
            continue
        try:
            df = read_legacy_file(path)
        except Exception as e:
            # One broken export shouldn't stop the others from landing
            print(f"FAILED  {path.name}: {e}")
            failed.append(path.name)
            continue

        production = production_from_filename(path)
        df["source_file"] = path.name
        df["production"] = production
        df["ingested_at"] = pd.Series([ingested_at] * len(df), dtype="datetime64[us, UTC]")

        # Overwrite, not append: running the job twice must give the same table
        write_deltalake(bronze_dir / production, df, mode="overwrite", schema_mode="overwrite")
        print(f"OK      {path.name}: {len(df)} rows -> bronze/{production}")

    return failed


if __name__ == "__main__":
    failed_files = ingest()
    sys.exit(1 if failed_files else 0)
