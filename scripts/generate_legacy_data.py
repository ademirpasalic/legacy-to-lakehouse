"""Generate messy, made-up legacy exports to migrate.

Simulates three productions whose staff each tracked shots their own way:
an old Excel export, a Google Sheets export and a Coda JSON export.
Different column names, status spellings, date formats and shot codes,
plus duplicates and blanks. All data is fake.

Usage:
    python scripts/generate_legacy_data.py
"""

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "legacy"
ARTISTS = ["Maja", "Jonas", "Sofie", "Emil", "Freja", "Oscar", "Ida", "Noah"]
DUPLICATE_RATE = 0.05
BLANK_RATE = 0.03


def maybe_blank(value, rng):
    return "" if rng.random() < BLANK_RATE else value


def with_duplicates(rows, rng):
    dupes = [dict(r) for r in rows if rng.random() < DUPLICATE_RATE]
    out = rows + dupes
    rng.shuffle(out)
    return out


def prod_039_excel(rng):
    """Old Excel sheet: Danish-ish headers, dd-mm-yyyy dates, mixed shot codes."""
    statuses = ["WIP", "igang", "done", "Færdig", "venter", "ikke startet"]
    rows = []
    for i in range(1, 61):
        code = rng.choice([f"sh{i * 10:03d}", f"SH_{i * 10:03d}", f"Shot {i * 10}"])
        due = date(2023, 3, 1) + timedelta(days=rng.randint(0, 120))
        rows.append({
            "Shot nr.": code,
            "Status": maybe_blank(rng.choice(statuses), rng),
            "Artist": maybe_blank(rng.choice(ARTISTS), rng),
            "Frames": maybe_blank(str(rng.randint(24, 240)), rng),
            "Deadline": maybe_blank(due.strftime("%d-%m-%Y"), rng),
        })
    return with_duplicates(rows, rng)


def prod_051_sheets(rng):
    """Google Sheets: English headers, ISO dates, zero-padded codes, short statuses."""
    statuses = ["in progress", "ip", "approved", "apr", "on hold", "not started"]
    rows = []
    for i in range(1, 81):
        due = date(2024, 9, 1) + timedelta(days=rng.randint(0, 150))
        rows.append({
            "Shot": f"SH{i * 10:04d}",
            "Task status": maybe_blank(rng.choice(statuses), rng),
            "Assigned to": maybe_blank(rng.choice(ARTISTS).lower(), rng),
            "Frame count": maybe_blank(str(rng.randint(24, 240)), rng),
            "Due date": maybe_blank(due.isoformat(), rng),
        })
    return with_duplicates(rows, rng)


def prod_077_coda(rng):
    """Coda JSON: nested-ish records, timestamps, frames sometimes as text."""
    statuses = ["In Progress", "Approved", "Not Started", "On Hold", "Final"]
    rows = []
    for i in range(1, 101):
        due = date(2026, 2, 1) + timedelta(days=rng.randint(0, 90))
        frames = rng.randint(24, 240)
        rows.append({
            "shot_code": f"sh_{i * 10:03d}",
            "state": maybe_blank(rng.choice(statuses), rng),
            "owner": {"name": maybe_blank(rng.choice(ARTISTS), rng)},
            "duration_frames": rng.choice([frames, f"{frames} fr", str(frames)]),
            "due": maybe_blank(f"{due.isoformat()}T00:00:00Z", rng),
        })
    return with_duplicates(rows, rng)


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    rng = random.Random(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    write_csv(OUT_DIR / "prod_039_shots_excel.csv", prod_039_excel(rng))
    write_csv(OUT_DIR / "prod_051_shots_sheets.csv", prod_051_sheets(rng))
    with (OUT_DIR / "prod_077_shots_coda.json").open("w", encoding="utf-8") as f:
        json.dump(prod_077_coda(rng), f, indent=2, ensure_ascii=False)

    for p in sorted(OUT_DIR.iterdir()):
        print(f"wrote {p.relative_to(OUT_DIR.parent.parent)}")


if __name__ == "__main__":
    main()
