# Legacy-to-Lakehouse Migration Kit

> Work in progress. Write this README in your own words as you build.

## The problem

Three productions tracked their shots in their own spreadsheets: an old Excel
file, a Google Sheet and a Coda doc. Different columns, different status
spellings, different date formats, duplicates and blanks. The goal is to move
all of it into one shared table that people can trust, and to prove that
nothing was lost on the way.

All data in this repo is made up (`scripts/generate_legacy_data.py`).

## Target schema (silver `shots`)

| column        | type    | notes                                              |
|---------------|---------|----------------------------------------------------|
| production    | string  | e.g. `prod_038`                                    |
| shot_code     | string  | normalised, e.g. `SH010`                           |
| status        | string  | `not_started`, `in_progress`, `on_hold`, `approved` |
| artist        | string  | nullable                                           |
| frame_count   | int     | nullable                                           |
| due_date      | date    | nullable                                           |

## Pipeline

```
data/legacy  ->  bronze (raw + metadata)  ->  silver (mapped + cleaned)  ->  reconcile
                                          \->  quarantine (rows that can't be fixed)
```

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python scripts/generate_legacy_data.py
python scripts/explore_formats.py
```

## Plan

- [ ] Step 0: explore Parquet and Delta (`scripts/explore_formats.py`)
- [ ] Step 1: bronze (`src/ingest_bronze.py`)
- [ ] Step 2: silver + quarantine (`src/transform_silver.py`)
- [ ] Step 3: reconciliation report (`src/reconcile.py`)
- [ ] Step 4: pytest tests + GitHub Actions
- [ ] Step 5: run the same pipeline in PySpark on Databricks Free Edition
- [ ] Step 6: raw files in S3 with a least-privilege IAM role

## Decisions and what I learned

_Write down why you did things the way you did. This is what interviewers ask about._
