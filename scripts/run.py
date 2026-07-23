import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.aggregate import aggregate_day, write_content_page
from scripts.poll import append_sighting, poll_once
from scripts.tar1090_feed import (
    append_chunk,
    finalize_other_days,
    write_receiver_json,
    write_snapshot,
    write_tar1090_day_page,
)


def main(
    raw_dir: Path,
    daily_dir: Path,
    content_dir: Path,
    tar1090_data_dir: Path,
    tar1090_chunks_dir: Path,
    tar1090_days_dir: Path,
    tar1090_days_content_dir: Path,
    now=None,
) -> None:
    now = now or datetime.now(timezone.utc)
    date = now.strftime("%Y-%m-%d")
    poll_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    raw_path = raw_dir / f"{date}.jsonl"
    response = poll_once()
    append_sighting(raw_path, poll_time, response)

    raw_lines = [json.loads(line) for line in raw_path.read_text().splitlines() if line]
    daily_data = aggregate_day(raw_lines, date)

    daily_dir.mkdir(parents=True, exist_ok=True)
    (daily_dir / f"{date}.json").write_text(json.dumps(daily_data, indent=2))

    write_content_page(date, len(daily_data["flights"]), content_dir)

    ac_list = response.get("ac", [])
    now_epoch_s = now.timestamp()
    write_snapshot(ac_list, now_epoch_s, tar1090_data_dir)
    append_chunk(ac_list, now_epoch_s, tar1090_chunks_dir)
    write_receiver_json(tar1090_data_dir)

    day_dir = tar1090_days_dir / date
    write_snapshot(ac_list, now_epoch_s, day_dir / "data")
    append_chunk(ac_list, now_epoch_s, day_dir / "chunks", retain=400)
    write_receiver_json(day_dir / "data")
    finalize_other_days(tar1090_days_dir, date, now_epoch_s)
    write_tar1090_day_page(date, tar1090_days_content_dir)


if __name__ == "__main__":
    main(
        Path("data/raw"),
        Path("data/daily"),
        Path("content/days"),
        Path("static/tar1090/data"),
        Path("static/tar1090/chunks"),
        Path("static/tar1090/days"),
        Path("content/tar1090days"),
    )
