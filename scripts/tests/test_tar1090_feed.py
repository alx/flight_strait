import json
from pathlib import Path

from scripts.tar1090_feed import append_chunk, write_receiver_json, write_snapshot

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
