import json
from pathlib import Path

from scripts.aggregate import aggregate_day, write_content_page

RAW_LINES = [
    {
        "poll_time": "2026-07-22T10:00:00Z",
        "aircraft": [
            {
                "hex": "abc123",
                "flight": "UAL123 ",
                "r": "N12345",
                "t": "B789",
                "lat": 40.2,
                "lon": 51.0,
                "alt_baro": 35000,
                "track": 90,
                "gs": 480,
            }
        ],
    },
    {
        "poll_time": "2026-07-22T10:05:00Z",
        "aircraft": [
            {
                "hex": "abc123",
                "flight": "UAL123 ",
                "r": "N12345",
                "t": "B789",
                "lat": 40.3,
                "lon": 51.8,
                "alt_baro": 35000,
                "track": 91,
                "gs": 481,
            }
        ],
    },
]


def test_aggregate_day_groups_by_hex_and_flight():
    result = aggregate_day(RAW_LINES, "2026-07-22")

    assert result["date"] == "2026-07-22"
    assert len(result["flights"]) == 1

    flight = result["flights"][0]
    assert flight["hex"] == "abc123"
    assert flight["flight"] == "UAL123"
    assert flight["registration"] == "N12345"
    assert flight["type"] == "B789"
    assert flight["first_seen"] == "2026-07-22T10:00:00Z"
    assert flight["last_seen"] == "2026-07-22T10:05:00Z"
    assert flight["alt_min"] == 35000
    assert flight["alt_max"] == 35000
    assert len(flight["track"]) == 2
    assert flight["closest_trabzon_nm"] > 0


def test_aggregate_day_with_no_sightings():
    result = aggregate_day([], "2026-07-22")
    assert result == {"date": "2026-07-22", "flights": []}


def test_write_content_page_creates_expected_front_matter(tmp_path):
    write_content_page("2026-07-22", 3, tmp_path)

    content = (tmp_path / "2026-07-22.md").read_text()
    assert 'title: "2026-07-22"' in content
    assert "date: 2026-07-22T00:00:00Z" in content
    assert "flight_count: 3" in content


def test_write_content_page_overwrites_existing_file(tmp_path):
    write_content_page("2026-07-22", 3, tmp_path)
    write_content_page("2026-07-22", 7, tmp_path)

    content = (tmp_path / "2026-07-22.md").read_text()
    assert "flight_count: 7" in content
