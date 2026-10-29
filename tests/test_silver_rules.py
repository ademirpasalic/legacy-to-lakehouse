import pytest

from src.transform_silver import clean_row, normalise_shot_code, parse_frames


@pytest.mark.parametrize("raw", ["sh010", "SH_010", "Shot 10", "SH0010", "sh_010", " sh010 "])
def test_shot_codes_from_every_source_end_up_the_same(raw):
    assert normalise_shot_code(raw) == "SH010"


@pytest.mark.parametrize("raw", ["", "010", "scene 10", "SH"])
def test_unknown_shot_codes_are_not_guessed(raw):
    assert normalise_shot_code(raw) is None


@pytest.mark.parametrize("raw, expected", [("120", 120), ("120 fr", 120), (" 120fr ", 120), ("", None)])
def test_frames(raw, expected):
    assert parse_frames(raw) == expected


def test_frames_that_are_not_numbers_raise():
    with pytest.raises(ValueError):
        parse_frames("about 120")


def row(**overrides):
    base = {"shot_code": "sh010", "status": "WIP", "artist": "maja", "frame_count": "48",
            "due_date": "22-06-2023"}
    return {**base, **overrides}


def test_clean_row_maps_everything():
    cleaned = clean_row(row(), "%d-%m-%Y")
    assert cleaned["shot_code"] == "SH010"
    assert cleaned["status"] == "in_progress"
    assert cleaned["artist"] == "Maja"
    assert cleaned["frame_count"] == 48
    assert str(cleaned["due_date"]) == "2023-06-22"


@pytest.mark.parametrize("overrides, reason", [
    ({"status": ""}, "status is missing"),
    ({"status": "Final"}, "not mapped"),
    ({"shot_code": "scene 10"}, "not recognised"),
])
def test_rows_that_cant_be_fixed_raise_with_a_reason(overrides, reason):
    with pytest.raises(ValueError, match=reason):
        clean_row(row(**overrides), "%d-%m-%Y")


def test_dates_in_the_wrong_format_raise():
    with pytest.raises(ValueError):
        clean_row(row(due_date="2023-06-22"), "%d-%m-%Y")
