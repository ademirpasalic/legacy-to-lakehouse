"""Silver: map and clean bronze into one shared shots table.

YOUR TASK
- Map each source's columns onto the target schema in the README.
- Normalise shot codes (sh010, SH_010, Shot 10, SH0010, sh_010 -> SH010).
- Map every status spelling onto: not_started, in_progress, on_hold, approved.
  Keep the mapping as data (a dict or a small table), not as if/else chains.
- Parse the three date formats into real dates.
- Turn "120 fr" and "120" into the integer 120.
- Remove duplicates.
- Rows that can't be fixed go to a quarantine table with a reason,
  instead of being dropped silently or crashing the run.
- Write data/silver/shots and data/silver/quarantine as Delta tables.

Questions to be able to answer in an interview:
- How did you decide what each legacy status meant?
- Why quarantine instead of failing the whole run?
"""
