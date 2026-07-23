import json
from datetime import datetime, timezone
from unittest.mock import patch

from scripts.run import main

FAKE_RESPONSE = {
    "ac": [
        {
            "hex": "abc123",
            "flight": "UAL123",
            "r": "N12345",
            "t": "B789",
            "lat": 40.2,
            "lon": 51.0,
            "alt_baro": 35000,
            "track": 90,
            "gs": 480,
        }
    ]
}


def _dirs(tmp_path):
    return dict(
        raw_dir=tmp_path / "data" / "raw",
        daily_dir=tmp_path / "data" / "daily",
        content_dir=tmp_path / "content" / "days",
        tar1090_data_dir=tmp_path / "tar1090" / "data",
        tar1090_chunks_dir=tmp_path / "tar1090" / "chunks",
        tar1090_days_dir=tmp_path / "tar1090" / "days",
        tar1090_days_content_dir=tmp_path / "content" / "tar1090days",
    )


@patch("scripts.run.poll_once", return_value=FAKE_RESPONSE)
def test_main_writes_raw_daily_and_content_files(mock_poll, tmp_path):
    dirs = _dirs(tmp_path)
    fixed_now = datetime(2026, 7, 22, 10, 0, 0, tzinfo=timezone.utc)

    main(**dirs, now=fixed_now)

    raw_file = dirs["raw_dir"] / "2026-07-22.jsonl"
    assert raw_file.exists()
    assert json.loads(raw_file.read_text().splitlines()[0])["aircraft"] == FAKE_RESPONSE["ac"]

    daily_file = dirs["daily_dir"] / "2026-07-22.json"
    daily_data = json.loads(daily_file.read_text())
    assert daily_data["date"] == "2026-07-22"
    assert len(daily_data["flights"]) == 1

    content_file = dirs["content_dir"] / "2026-07-22.md"
    assert "flight_count: 1" in content_file.read_text()


@patch("scripts.run.poll_once", return_value=FAKE_RESPONSE)
def test_main_writes_tar1090_feed_files(mock_poll, tmp_path):
    dirs = _dirs(tmp_path)
    fixed_now = datetime(2026, 7, 22, 10, 0, 0, tzinfo=timezone.utc)

    main(**dirs, now=fixed_now)

    aircraft_json = json.loads((dirs["tar1090_data_dir"] / "aircraft.json").read_text())
    assert aircraft_json["aircraft"] == FAKE_RESPONSE["ac"]
    assert aircraft_json["now"] == fixed_now.timestamp()

    receiver_json = json.loads((dirs["tar1090_data_dir"] / "receiver.json").read_text())
    assert receiver_json["lat"] == 40.995

    chunks_index = json.loads((dirs["tar1090_chunks_dir"] / "chunks.json").read_text())
    assert len(chunks_index["chunks"]) == 1
    chunk_file = dirs["tar1090_chunks_dir"] / chunks_index["chunks"][0]
    assert chunk_file.exists()
    assert json.loads(chunk_file.read_text())["aircraft"] == FAKE_RESPONSE["ac"]


@patch("scripts.run.poll_once", return_value=FAKE_RESPONSE)
def test_main_writes_tar1090_day_page(mock_poll, tmp_path):
    dirs = _dirs(tmp_path)
    fixed_now = datetime(2026, 7, 22, 10, 0, 0, tzinfo=timezone.utc)

    main(**dirs, now=fixed_now)

    day_dir = dirs["tar1090_days_dir"] / "2026-07-22"
    aircraft_json = json.loads((day_dir / "data" / "aircraft.json").read_text())
    assert aircraft_json["aircraft"] == FAKE_RESPONSE["ac"]

    chunks_index = json.loads((day_dir / "chunks" / "chunks.json").read_text())
    assert len(chunks_index["chunks"]) == 1

    day_page = dirs["tar1090_days_content_dir"] / "2026-07-22.md"
    assert 'title: "2026-07-22"' in day_page.read_text()


@patch("scripts.run.poll_once", return_value=FAKE_RESPONSE)
def test_main_finalizes_previous_day_on_rollover(mock_poll, tmp_path):
    dirs = _dirs(tmp_path)
    day_one = datetime(2026, 7, 22, 23, 55, 0, tzinfo=timezone.utc)
    day_two = datetime(2026, 7, 23, 0, 0, 0, tzinfo=timezone.utc)

    main(**dirs, now=day_one)
    main(**dirs, now=day_two)

    finalized = json.loads(
        (dirs["tar1090_days_dir"] / "2026-07-22" / "data" / "aircraft.json").read_text()
    )
    assert finalized["aircraft"] == []

    today = json.loads(
        (dirs["tar1090_days_dir"] / "2026-07-23" / "data" / "aircraft.json").read_text()
    )
    assert today["aircraft"] == FAKE_RESPONSE["ac"]
