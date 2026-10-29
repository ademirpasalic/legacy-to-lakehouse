"""Silver: map and clean bronze into one shared shots table.

Each production tracked shots its own way, so every source gets a small
mapping (column names and date format). After that all rows go through the
same rules. Rows that can't be fixed go to a quarantine table with a reason,
so nothing is dropped silently and one bad row doesn't stop the run.

The shots table is written with MERGE on (production, shot_code), so running
the job again updates existing shots instead of adding duplicates.

Usage:
    python -m src.transform_silver
"""

import json
import re
from pathlib import Path

import pandas as pd
import pyarrow as pa
from deltalake import DeltaTable, write_deltalake

ROOT = Path(__file__).resolve().parent.parent
BRONZE_DIR = ROOT / "data" / "bronze"
SILVER_DIR = ROOT / "data" / "silver"

# How each production named its columns, and how it wrote dates
SOURCES = {
    "prod_039": {
        "columns": {"Shot nr.": "shot_code", "Status": "status", "Artist": "artist",
                    "Frames": "frame_count", "Deadline": "due_date"},
        "date_format": "%d-%m-%Y",
    },
    "prod_051": {
        "columns": {"Shot": "shot_code", "Task status": "status", "Assigned to": "artist",
                    "Frame count": "frame_count", "Due date": "due_date"},
        "date_format": "%Y-%m-%d",
    },
    "prod_077": {
        "columns": {"shot_code": "shot_code", "state": "status", "owner.name": "artist",
                    "duration_frames": "frame_count", "due": "due_date"},
        "date_format": "%Y-%m-%dT%H:%M:%SZ",
    },
}

# Every legacy status spelling we have agreed on, mapped to the target status.
# "Final" (prod_077) is left out on purpose: it could mean approved or delivered,
# so those rows go to quarantine until the production team decides.
STATUS_MAP = {
    "wip": "in_progress", "igang": "in_progress", "in progress": "in_progress", "ip": "in_progress",
    "done": "approved", "færdig": "approved", "approved": "approved", "apr": "approved",
    "venter": "on_hold", "on hold": "on_hold",
    "ikke startet": "not_started", "not started": "not_started",
}

SHOT_CODE_PATTERN = re.compile(r"^(?:sh|shot)[\s_]*0*(\d+)$", re.IGNORECASE)

SILVER_SCHEMA = pa.schema([
    ("production", pa.string()),
    ("shot_code", pa.string()),
    ("status", pa.string()),
    ("artist", pa.string()),
    ("frame_count", pa.int32()),
    ("due_date", pa.date32()),
    ("source_file", pa.string()),
])

QUARANTINE_SCHEMA = pa.schema([
    ("production", pa.string()),
    ("source_file", pa.string()),
    ("shot_key", pa.string()),
    ("reason", pa.string()),
    ("raw_row", pa.string()),
])


def normalise_shot_code(raw: str) -> str | None:
    """sh010, SH_010, Shot 10, SH0010, sh_010 -> SH010. None if it isn't a shot code."""
    match = SHOT_CODE_PATTERN.match(raw.strip())
    if not match:
        return None
    return f"SH{int(match.group(1)):03d}"


def parse_frames(raw: str) -> int | None:
    """'120', '120 fr' -> 120. Blank -> None. Raises ValueError for anything else."""
    value = raw.strip().lower().removesuffix("fr").strip()
    if value == "":
        return None
    if not value.isdigit():
        raise ValueError(f"frame count '{raw}' is not a number")
    return int(value)


def parse_date(raw: str, date_format: str):
    """Blank -> None. Raises ValueError if the date doesn't match the source's format."""
    if raw.strip() == "":
        return None
    return pd.to_datetime(raw.strip(), format=date_format).date()


def clean_row(row: dict, date_format: str) -> dict:
    """Turn one mapped legacy row into a silver row. Raises ValueError with the reason."""
    shot_code = normalise_shot_code(row["shot_code"])
    if shot_code is None:
        raise ValueError(f"shot code '{row['shot_code']}' not recognised")

    status_raw = row["status"].strip().lower()
    if status_raw == "":
        raise ValueError("status is missing")
    if status_raw not in STATUS_MAP:
        raise ValueError(f"status '{row['status']}' is not mapped yet")

    artist = row["artist"].strip()
    return {
        "shot_code": shot_code,
        "status": STATUS_MAP[status_raw],
        "artist": artist.capitalize() if artist else None,
        "frame_count": parse_frames(row["frame_count"]),
        "due_date": parse_date(row["due_date"], date_format),
    }


def transform_production(bronze: pd.DataFrame, production: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split one production's bronze rows into clean silver rows and quarantined rows."""
    source = SOURCES[production]
    mapped = bronze.rename(columns=source["columns"])
    good, bad = [], []

    for raw, row in zip(bronze.to_dict("records"), mapped.to_dict("records")):
        base = {"production": production, "source_file": row["source_file"]}
        try:
            good.append({**base, **clean_row(row, source["date_format"])})
        except ValueError as e:
            raw.pop("ingested_at", None)
            bad.append({
                **base,
                "shot_key": normalise_shot_code(row["shot_code"]) or row["shot_code"],
                "reason": str(e),
                "raw_row": json.dumps(raw, ensure_ascii=False),
            })

    silver = pd.DataFrame(good, columns=SILVER_SCHEMA.names)
    quarantine = pd.DataFrame(bad, columns=QUARANTINE_SCHEMA.names)

    # Exact copies are just duplicates. The same shot with different values is a
    # conflict nobody can resolve automatically, so all its rows go to quarantine.
    silver = silver.drop_duplicates()
    conflicts = silver[silver.duplicated(["production", "shot_code"], keep=False)]
    if not conflicts.empty:
        silver = silver.drop(conflicts.index)
        quarantine = pd.concat([quarantine, pd.DataFrame({
            "production": conflicts["production"],
            "source_file": conflicts["source_file"],
            "shot_key": conflicts["shot_code"],
            "reason": "same shot appears with different values",
            "raw_row": conflicts.astype(str).to_json(orient="records", lines=True).splitlines(),
        })], ignore_index=True)

    return silver, quarantine


def merge_into_silver(silver: pd.DataFrame, table_path: Path) -> None:
    """Upsert on (production, shot_code): update shots we have, insert new ones."""
    source = pa.Table.from_pandas(silver, schema=SILVER_SCHEMA, preserve_index=False)
    if not DeltaTable.is_deltatable(str(table_path)):
        write_deltalake(table_path, source)
        return
    (
        DeltaTable(table_path)
        .merge(
            source=source,
            predicate="t.production = s.production AND t.shot_code = s.shot_code",
            source_alias="s",
            target_alias="t",
        )
        .when_matched_update_all()
        .when_not_matched_insert_all()
        .execute()
    )


def transform(bronze_dir: Path = BRONZE_DIR, silver_dir: Path = SILVER_DIR) -> None:
    all_silver, all_quarantine = [], []
    for production in SOURCES:
        table_path = bronze_dir / production
        if not DeltaTable.is_deltatable(str(table_path)):
            print(f"SKIP    {production}: no bronze table")
            continue
        bronze = DeltaTable(table_path).to_pandas()
        silver, quarantine = transform_production(bronze, production)
        all_silver.append(silver)
        all_quarantine.append(quarantine)
        print(f"OK      {production}: {len(bronze)} bronze rows -> "
              f"{len(silver)} shots, {len(quarantine)} quarantined")

    merge_into_silver(pd.concat(all_silver, ignore_index=True), silver_dir / "shots")

    # Quarantine is the current list of problems, so it's replaced on every run
    quarantine = pa.Table.from_pandas(pd.concat(all_quarantine, ignore_index=True),
                                      schema=QUARANTINE_SCHEMA, preserve_index=False)
    write_deltalake(silver_dir / "quarantine", quarantine, mode="overwrite")


if __name__ == "__main__":
    transform()
