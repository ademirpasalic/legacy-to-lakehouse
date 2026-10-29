# Legacy-to-Lakehouse Migration Kit

A practice data migration. Three productions tracked their shots in their own spreadsheets: an old Excel file, a Google Sheet and a Coda doc. Different columns, different status spellings, different date formats, duplicates and blanks. This repo moves all of it into one shared Delta Lake table, puts the rows that can't be fixed in a quarantine table, and checks that nothing was lost on the way.

It's based on a real migration I did at work, moving production staff from
their own sheets into one shared system. All data in this repo is made up
(`scripts/generate_legacy_data.py`).

## Pipeline

```
data/legacy  ->  bronze (raw + metadata)  ->  silver (mapped + cleaned)  ->  reconcile
                                          \->  quarantine (rows that can't be fixed)
```

| Step | File | What it does |
|---|---|---|
| Bronze | `src/ingest_bronze.py` | Lands each export as-is (all text) in its own Delta table, with `source_file`, `production` and `ingested_at` |
| Silver | `src/transform_silver.py` | Maps each source's columns to one schema, cleans the values, and MERGEs into `silver/shots`. Bad rows go to `silver/quarantine` with a reason |
| Reconcile | `src/reconcile.py` | Counts shots in the legacy files and checks they all ended up in silver or quarantine, never both. Exits with 1 if not |

## Target schema (silver `shots`)

| column        | type    | notes                                               |
|---------------|---------|-----------------------------------------------------|
| production    | string  | e.g. `prod_039`                                     |
| shot_code     | string  | normalised, e.g. `SH010`                            |
| status        | string  | `not_started`, `in_progress`, `on_hold`, `approved` |
| artist        | string  | nullable                                            |
| frame_count   | int     | nullable                                            |
| due_date      | date    | nullable                                            |
| source_file   | string  | which legacy file the row came from                 |

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python scripts/generate_legacy_data.py
python -m src.ingest_bronze
python -m src.transform_silver
python -m src.reconcile
pytest
```

Result on the generated data:

```
production   legacy rows  legacy shots  silver  quarantine  result
prod_039              61            60      58           2  OK
prod_051              88            80      75           5  OK
prod_077             104           100      83          17  OK

Quarantine reasons:
     17  status '...' is not mapped yet
      9  status is missing
```

GitHub Actions runs the tests, the migration and the reconciliation on every push.

## Decisions

- **Bronze keeps everything as text.** If pandas guesses types, `007` becomes `7`
  and dates change format before anyone has looked at them. Keeping the raw
  values means I can always go back and check what the legacy system said.
- **Overwrite in bronze, MERGE in silver.** Running the job twice must give the
  same result. Bronze is a copy of the latest export, so it's overwritten.
  Silver is upserted on `(production, shot_code)`, so existing shots are updated
  and new ones are added, never duplicated.
- **The mappings are data, not code.** Each source has a small dict of column
  names and a date format, and all status spellings live in one `STATUS_MAP`.
  Adding a fourth production means adding a mapping, not new if/else branches.
- **Quarantine instead of failing or dropping.** One bad row shouldn't stop the
  migration, and it shouldn't disappear either. Each quarantined row keeps its
  raw values and a reason, so someone can fix it at the source.
- **I don't guess.** Coda's `Final` status could mean approved or delivered, so
  it isn't in the map. Those rows wait in quarantine until the production team
  decides. Same with rows that have no status at all.
- **Reconciliation reads the legacy files, not bronze.** If bronze had a bug,
  checking against it would hide it.
- **Exact duplicates are removed. Conflicting duplicates are quarantined.** If the
  same shot appears twice with different values, there's no safe way to pick one.

## Next steps

- [ ] Run the same pipeline in PySpark on Databricks Free Edition
- [ ] A gold layer with a few SQL views for producers (status per production, overdue shots)
- [ ] Delete shots from silver that were removed from the source or moved to
  quarantine. The MERGE only updates and inserts today, so reconcile catches
  these cases but the pipeline doesn't fix them yet
- [ ] Handle a schema change, e.g. a source that renames a column
- [ ] Raw files in S3 with a least-privilege IAM role
