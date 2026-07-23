import json
from pathlib import Path

from scripts.tar1090_feed import (
    append_chunk,
    finalize_other_days,
    write_receiver_json,
    write_snapshot,
    write_tar1090_day_page,
)

AC_LIST = [
    {
        "hex": "abc123",
        "flight": "THA901",
        "lat": 40.2,
        "lon": 39.5,
        "alt_baro": 35000,
        "gs": 480,
        "track": 90,
    }
]


def test_write_snapshot_creates_aircraft_json(tmp_path):
    write_snapshot(AC_LIST, 1753171200.0, tmp_path)

    data = json.loads((tmp_path / "aircraft.json").read_text())
    assert data["now"] == 1753171200.0
    assert data["aircraft"] == AC_LIST


def test_write_receiver_json_creates_expected_file(tmp_path):
    write_receiver_json(tmp_path)

    data = json.loads((tmp_path / "receiver.json").read_text())
    assert data["lat"] == 40.995
    assert data["lon"] == 39.789


def test_append_chunk_creates_chunk_file_and_index(tmp_path):
    append_chunk(AC_LIST, 1753171200.0, tmp_path)

    index = json.loads((tmp_path / "chunks.json").read_text())
    assert index["chunks"] == ["chunk_1753171200000.json"]

    chunk = json.loads((tmp_path / "chunk_1753171200000.json").read_text())
    assert chunk["now"] == 1753171200.0
    assert chunk["aircraft"] == AC_LIST


def test_append_chunk_accumulates_multiple_chunks_in_order(tmp_path):
    append_chunk(AC_LIST, 1753171200.0, tmp_path)
    append_chunk(AC_LIST, 1753171500.0, tmp_path)

    index = json.loads((tmp_path / "chunks.json").read_text())
    assert index["chunks"] == [
        "chunk_1753171200000.json",
        "chunk_1753171500000.json",
    ]


def test_append_chunk_prunes_beyond_retain(tmp_path):
    append_chunk(AC_LIST, 1753171200.0, tmp_path, retain=2)
    append_chunk(AC_LIST, 1753171500.0, tmp_path, retain=2)
    append_chunk(AC_LIST, 1753171800.0, tmp_path, retain=2)

    index = json.loads((tmp_path / "chunks.json").read_text())
    assert index["chunks"] == [
        "chunk_1753171500000.json",
        "chunk_1753171800000.json",
    ]
    assert not (tmp_path / "chunk_1753171200000.json").exists()
    assert (tmp_path / "chunk_1753171500000.json").exists()
    assert (tmp_path / "chunk_1753171800000.json").exists()


def test_write_tar1090_day_page_creates_expected_front_matter(tmp_path):
    write_tar1090_day_page("2026-07-22", tmp_path)

    content = (tmp_path / "2026-07-22.md").read_text()
    assert 'title: "2026-07-22"' in content
    assert "date: 2026-07-22T00:00:00Z" in content


def test_finalize_other_days_empties_non_today_aircraft_json(tmp_path):
    days_root = tmp_path

    (days_root / "2026-07-22" / "data").mkdir(parents=True)
    (days_root / "2026-07-22" / "data" / "aircraft.json").write_text(
        json.dumps({"now": 1.0, "messages": 0, "aircraft": AC_LIST})
    )
    (days_root / "2026-07-23" / "data").mkdir(parents=True)
    (days_root / "2026-07-23" / "data" / "aircraft.json").write_text(
        json.dumps({"now": 1.0, "messages": 0, "aircraft": AC_LIST})
    )

    finalize_other_days(days_root, "2026-07-23", 1753260000.0)

    finalized = json.loads((days_root / "2026-07-22" / "data" / "aircraft.json").read_text())
    assert finalized["aircraft"] == []
    assert finalized["now"] == 1753260000.0

    untouched = json.loads((days_root / "2026-07-23" / "data" / "aircraft.json").read_text())
    assert untouched["aircraft"] == AC_LIST


def test_finalize_other_days_noop_when_days_root_missing(tmp_path):
    finalize_other_days(tmp_path / "missing", "2026-07-23", 1753260000.0)
