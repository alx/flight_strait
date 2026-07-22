import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.aggregate import aggregate_day, write_content_page
from scripts.poll import append_sighting, poll_once


def main(raw_dir: Path, daily_dir: Path, content_dir: Path, now=None) -> None:
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


if __name__ == "__main__":
    main(Path("data/raw"), Path("data/daily"), Path("content/days"))
