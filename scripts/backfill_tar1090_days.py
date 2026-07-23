import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.tar1090_feed import (
    append_chunk,
    write_receiver_json,
    write_snapshot,
    write_tar1090_day_page,
)


def backfill_day(date: str, raw_path: Path, tar1090_days_dir: Path, content_dir: Path) -> None:
    day_dir = tar1090_days_dir / date
    lines = [json.loads(line) for line in raw_path.read_text().splitlines() if line]

    last_epoch_s = 0.0
    for entry in lines:
        poll_dt = datetime.strptime(entry["poll_time"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        epoch_s = poll_dt.timestamp()
        last_epoch_s = epoch_s
        append_chunk(entry["aircraft"], epoch_s, day_dir / "chunks", retain=400)

    write_receiver_json(day_dir / "data")
    write_snapshot([], last_epoch_s, day_dir / "data")
    write_tar1090_day_page(date, content_dir)


def backfill_all(raw_dir: Path, tar1090_days_dir: Path, content_dir: Path, skip_date: str) -> None:
    for raw_path in sorted(raw_dir.glob("*.jsonl")):
        date = raw_path.stem
        if date == skip_date:
            continue
        backfill_day(date, raw_path, tar1090_days_dir, content_dir)


if __name__ == "__main__":
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backfill_all(
        Path("data/raw"),
        Path("static/tar1090/days"),
        Path("content/tar1090days"),
        skip_date=today,
    )
