"""Reconciliation: prove nothing was lost or invented in the migration.

Counts are taken from the legacy files themselves, not from bronze, so a bug
in an earlier step can't hide itself. For every production:

    unique legacy shots == shots in silver + shots in quarantine

and no shot may be in both. The script exits with code 1 if anything is off,
so CI fails when the migration is wrong.

Usage:
    python -m src.reconcile
"""

import sys
from pathlib import Path

from deltalake import DeltaTable

from src.ingest_bronze import LEGACY_DIR, production_from_filename, read_legacy_file
from src.transform_silver import SILVER_DIR, SOURCES, normalise_shot_code


def read_legacy_shots(legacy_dir: Path) -> dict[str, tuple[int, set[str]]]:
    """Per production: (number of legacy rows, set of unique shots)."""
    result = {}
    for path in sorted(legacy_dir.glob("*")):
        if path.suffix not in (".csv", ".json"):
            continue
        production = production_from_filename(path)
        shot_column = next(raw for raw, target in SOURCES[production]["columns"].items()
                           if target == "shot_code")
        row_codes = read_legacy_file(path)[shot_column]  # one per row, duplicates included
        # Unrecognised codes are kept as-is, so they are still counted
        unique_shots = {normalise_shot_code(code) or code for code in row_codes}
        result[production] = (len(row_codes), unique_shots)
    return result


def reconcile(legacy_dir: Path = LEGACY_DIR, silver_dir: Path = SILVER_DIR) -> bool:
    silver = DeltaTable(silver_dir / "shots").to_pandas()
    quarantine = DeltaTable(silver_dir / "quarantine").to_pandas()
    all_ok = True

    print(f"{'production':<12}{'legacy rows':>12}{'legacy shots':>14}{'silver':>8}"
          f"{'quarantine':>12}  result")
    for production, (legacy_rows, legacy_shots) in read_legacy_shots(legacy_dir).items():
        silver_shots = set(silver.loc[silver["production"] == production, "shot_code"])
        quarantine_shots = set(quarantine.loc[quarantine["production"] == production, "shot_key"])

        missing = legacy_shots - silver_shots - quarantine_shots
        invented = (silver_shots | quarantine_shots) - legacy_shots
        in_both = silver_shots & quarantine_shots
        ok = not missing and not invented and not in_both and \
            len(legacy_shots) == len(silver_shots) + len(quarantine_shots)
        all_ok = all_ok and ok

        print(f"{production:<12}{legacy_rows:>12}{len(legacy_shots):>14}{len(silver_shots):>8}"
              f"{len(quarantine_shots):>12}  {'OK' if ok else 'MISMATCH'}")
        for label, shots in (("missing", missing), ("invented", invented), ("in both", in_both)):
            if shots:
                print(f"    {label}: {', '.join(sorted(shots))}")

    print("\nQuarantine reasons:")
    for reason, count in quarantine["reason"].str.replace(r"'.*'", "'...'", regex=True) \
            .value_counts().items():
        print(f"    {count:>3}  {reason}")

    return all_ok


if __name__ == "__main__":
    sys.exit(0 if reconcile() else 1)
