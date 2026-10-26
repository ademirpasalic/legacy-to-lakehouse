"""Bronze: land the legacy exports as-is, plus where and when they came from.

YOUR TASK
- Read every file in data/legacy/ (CSV and JSON).
- Keep the original columns and values untouched. No cleaning here.
- Add metadata columns: source_file, production, ingested_at.
- Write one Delta table per source to data/bronze/.
- Running it twice must not create duplicates (think: overwrite vs append).

Questions to be able to answer in an interview:
- Why keep the raw data instead of cleaning it straight away?
- What happens if one of the files is broken?
"""
