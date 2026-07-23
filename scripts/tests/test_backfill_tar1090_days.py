import json
from pathlib import Path

from scripts.backfill_tar1090_days import backfill_all, backfill_day

RAW_LINES = [
    {"poll_time": "2026-07-22T10:00:00Z", "aircraft": [{"hex": "abc123", "flight": "UAL123"}]},
    {"poll_time": "2026-07-22T10:05:00Z", "aircraft": [{"hex": "abc123", "flight": "UAL123"}]},
]


def _write_raw(path: Path, lines: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")


def test_backfill_day_writes_chunks_and_finalized_snapshot(tmp_path):
    raw_path = tmp_path / "raw" / "2026-07-22.jsonl"
    _write_raw(raw_path, RAW_LINES)
    days_dir = tmp_path / "days"
    content_dir = tmp_path / "content"

    backfill_day("2026-07-22", raw_path, days_dir, content_dir)

    chunks_index = json.loads((days_dir / "2026-07-22" / "chunks" / "chunks.json").read_text())
    assert len(chunks_index["chunks"]) == 2

    aircraft_json = json.loads((days_dir / "2026-07-22" / "data" / "aircraft.json").read_text())
    assert aircraft_json["aircraft"] == []

    assert (content_dir / "2026-07-22.md").exists()


def test_backfill_day_is_idempotent_on_rerun(tmp_path):
    raw_path = tmp_path / "raw" / "2026-07-22.jsonl"
    _write_raw(raw_path, RAW_LINES)
    days_dir = tmp_path / "days"
    content_dir = tmp_path / "content"

    backfill_day("2026-07-22", raw_path, days_dir, content_dir)
    backfill_day("2026-07-22", raw_path, days_dir, content_dir)

    chunks_index = json.loads((days_dir / "2026-07-22" / "chunks" / "chunks.json").read_text())
    assert len(chunks_index["chunks"]) == 2


def test_backfill_all_skips_the_given_date(tmp_path):
    raw_dir = tmp_path / "raw"
    _write_raw(raw_dir / "2026-07-22.jsonl", RAW_LINES)
    _write_raw(raw_dir / "2026-07-23.jsonl", RAW_LINES)
    days_dir = tmp_path / "days"
    content_dir = tmp_path / "content"

    backfill_all(raw_dir, days_dir, content_dir, skip_date="2026-07-23")

    assert (days_dir / "2026-07-22").exists()
    assert not (days_dir / "2026-07-23").exists()
