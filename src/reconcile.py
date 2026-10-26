"""Reconciliation: prove nothing was lost or invented in the migration.

YOUR TASK
- Per production: rows in legacy, unique shots in legacy,
  rows in silver, rows in quarantine.
- Check: unique legacy shots == silver shots + quarantined shots.
- List any shot that exists in legacy but nowhere after migration.
- Print a short report and exit with an error code if the numbers don't match,
  so CI fails when the migration is wrong.

Questions to be able to answer in an interview:
- When would you be confident enough to switch the legacy source off?
  (Compare: the Google Sheet you retired when activity dropped to zero.)
"""
