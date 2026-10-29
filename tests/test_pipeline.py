"""Run the whole migration on a tiny legacy export and check the results."""

from deltalake import DeltaTable

from src.ingest_bronze import ingest
from src.reconcile import reconcile
from src.transform_silver import transform

LEGACY_CSV = """Shot nr.,Status,Artist,Frames,Deadline
sh010,WIP,Maja,48,22-06-2023
SH_020,Færdig,,120,
Shot 30,,Emil,24,01-07-2023
sh010,WIP,Maja,48,22-06-2023
"""


def run_migration(tmp_path):
    legacy, bronze, silver = tmp_path / "legacy", tmp_path / "bronze", tmp_path / "silver"
    legacy.mkdir()
    (legacy / "prod_039_shots_excel.csv").write_text(LEGACY_CSV, encoding="utf-8")
    assert ingest(legacy, bronze) == []
    transform(bronze, silver)
    return legacy, silver


def test_clean_rows_land_in_silver_and_bad_rows_in_quarantine(tmp_path):
    _, silver = run_migration(tmp_path)
    shots = DeltaTable(silver / "shots").to_pandas()
    quarantine = DeltaTable(silver / "quarantine").to_pandas()

    assert sorted(shots["shot_code"]) == ["SH010", "SH020"]  # duplicate SH010 removed
    assert list(quarantine["shot_key"]) == ["SH030"]
    assert quarantine["reason"][0] == "status is missing"


def test_running_twice_gives_the_same_result(tmp_path):
    run_migration(tmp_path)
    legacy, silver = tmp_path / "legacy", tmp_path / "silver"
    transform(tmp_path / "bronze", silver)

    assert len(DeltaTable(silver / "shots").to_pandas()) == 2
    assert reconcile(legacy, silver)


def test_reconcile_fails_when_a_shot_goes_missing(tmp_path):
    legacy, silver = run_migration(tmp_path)
    DeltaTable(silver / "shots").delete("shot_code = 'SH020'")

    assert not reconcile(legacy, silver)
