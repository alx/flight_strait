# tar1090 Per-Day Trace Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a permanent, per-calendar-day tar1090 trace view at `/tar1090/days/<date>/` for every day in the archive, alongside the existing rolling 24h live view (`/tar1090/`) and the existing Leaflet day archive (`/days/<date>/`).

**Architecture:** Reuse the existing `scripts/tar1090_feed.py` snapshot/chunk-history functions a second time per poll, writing into a per-date directory (`static/tar1090/days/<date>/`) with no pruning. A thin Hugo-rendered page at the same public path reuses the shared, unmodified vendored `static/tar1090/` JS/CSS/assets via `relURL`, so no per-day duplication of the ~5.5MB vendored tree. A one-time backfill script covers days that predate this feature.

**Tech Stack:** Same as the existing project (Python 3 + `requests`, pytest, Hugo static site, GitHub Actions). No new runtime dependency.

## Global Constraints

- Trabzon reference point / `TRABZON` constant: reuse from `scripts.aggregate`, never redefine (existing project rule).
- Daily chunk retention: pass `append_chunk`'s `retain` parameter a fixed ceiling of `400` for per-day chunks (a day naturally produces at most ~288 five-minute-cadence chunks — 400 is a safety margin against runaway growth, not a real limit; no chunk in a normal day is ever actually pruned).
- Day finalization is idempotent and stateless: on every poll, every `static/tar1090/days/<date>/` directory except today's gets its `data/aircraft.json` overwritten to an empty aircraft list. No "previous date" state is tracked anywhere.
- No modifications to any vendored tar1090 file (`static/tar1090/script.js`, `early.js`, `config.js`, etc.) — the per-day views are pure data plus one new Hugo-rendered shell, never a change to tar1090 itself.
- Retention is permanent ("all days, forever") — no automatic pruning of `static/tar1090/days/<date>/` directories once created.
- This is purely additive — the existing rolling live view (`/tar1090/`) and the existing per-day Leaflet archive (`/days/<date>/`) are unchanged in behavior.

---

### Task 1: `scripts/tar1090_feed.py` — day content page and finalization

**Files:**
- Modify: `scripts/tar1090_feed.py`
- Modify: `scripts/tests/test_tar1090_feed.py`

**Interfaces:**
- Consumes: `write_snapshot(ac_list, now_epoch_s, data_dir)` (already exists in this file).
- Produces:
  - `write_tar1090_day_page(date: str, content_dir: Path) -> None` — consumed by Task 2 (`run.py`) and Task 5 (backfill script).
  - `finalize_other_days(days_root: Path, today: str, now_epoch_s: float) -> None` — consumed by Task 2 (`run.py`).

- [ ] **Step 1: Write the failing tests**

Add to the bottom of `scripts/tests/test_tar1090_feed.py` (keep the existing imports and tests, extend the import line):

```python
from scripts.tar1090_feed import (
    append_chunk,
    finalize_other_days,
    write_receiver_json,
    write_snapshot,
    write_tar1090_day_page,
)
```

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest scripts/tests/test_tar1090_feed.py -v`
Expected: FAIL with `ImportError: cannot import name 'finalize_other_days'` (or `'write_tar1090_day_page'`).

- [ ] **Step 3: Implement the two new functions**

Append to `scripts/tar1090_feed.py`:

```python
def write_tar1090_day_page(date: str, content_dir: Path) -> None:
    content_dir.mkdir(parents=True, exist_ok=True)
    page_path = content_dir / f"{date}.md"
    page_path.write_text(f'---\ntitle: "{date}"\ndate: {date}T00:00:00Z\n---\n')


def finalize_other_days(days_root: Path, today: str, now_epoch_s: float) -> None:
    if not days_root.exists():
        return
    for day_dir in sorted(days_root.iterdir()):
        if not day_dir.is_dir() or day_dir.name == today:
            continue
        write_snapshot([], now_epoch_s, day_dir / "data")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest scripts/tests/test_tar1090_feed.py -v`
Expected: 8 passed (5 pre-existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add scripts/tar1090_feed.py scripts/tests/test_tar1090_feed.py
git commit -m "Add tar1090 day-page front matter and day finalization"
```

---

### Task 2: Wire per-day writes and finalization into `scripts/run.py`

**Files:**
- Modify: `scripts/run.py` (full current content shown below)
- Modify: `scripts/tests/test_run.py` (full current content shown below)

**Interfaces:**
- Consumes: `append_chunk`, `write_receiver_json`, `write_snapshot`, `finalize_other_days`, `write_tar1090_day_page` from `scripts.tar1090_feed` (Task 1 for the new two).
- Produces: `main(raw_dir, daily_dir, content_dir, tar1090_data_dir, tar1090_chunks_dir, tar1090_days_dir, tar1090_days_content_dir, now=None) -> None` — new signature, consumed by Task 5 (backfill reuses the same `tar1090_feed` functions directly, not `main`) and Task 6 (`__main__` block / GitHub Actions, via `python -m scripts.run`).

- [ ] **Step 1: Update the test first**

Replace the full content of `scripts/tests/test_run.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest scripts/tests/test_run.py -v`
Expected: FAIL — all four tests fail with a `TypeError` (missing required positional arguments), since `main()` doesn't yet accept `tar1090_days_dir` / `tar1090_days_content_dir`.

- [ ] **Step 3: Update `scripts/run.py`**

Replace the full content of `scripts/run.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest scripts/tests/test_run.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run the full test suite**

Run: `PYTHONPATH=. pytest scripts/tests -v`
Expected: all tests pass (19 total: 8 from `test_tar1090_feed.py`, 4 from `test_run.py`, 7 pre-existing from `test_geo.py`/`test_aggregate.py`/`test_poll.py`).

- [ ] **Step 6: Commit**

```bash
git add scripts/run.py scripts/tests/test_run.py
git commit -m "Wire per-day tar1090 writes and finalization into the pipeline"
```

---

### Task 3: Hugo per-day shell and day index page

**Files:**
- Modify: `hugo.toml`
- Create: `content/tar1090days/_index.md`
- Create: `layouts/tar1090days/list.html`
- Create: `layouts/tar1090days/single.html` (generated from `static/tar1090/index.html`, see Step 3)

**Interfaces:**
- Consumes: `static/tar1090/{script.js,style.css,config.js,libs/,images/,...}` (existing, unmodified vendored assets).
- Consumes: `content/tar1090days/<date>.md` front matter (`title`, `date`) — produced at runtime by Task 2 (`write_tar1090_day_page`) and Task 5 (backfill).
- Produces: `/tar1090/days/<date>/index.html` (per-day shell) and `/tar1090/days/index.html` (list page), consumed by Task 4 (cross-link) and Task 6 (end-to-end verification).

- [ ] **Step 1: Add the permalink mapping**

In `hugo.toml`, add a new top-level table (anywhere after the existing `[params]` block):

```toml
[permalinks]
  tar1090days = "/tar1090/days/:slug/"
```

- [ ] **Step 2: Create the day index content and list template**

Create `content/tar1090days/_index.md`:

```markdown
---
title: "Daily Live Views"
url: /tar1090/days/
---
```

Create `layouts/tar1090days/list.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ .Title }} &mdash; {{ .Site.Title }}</title>
</head>
<body>
  <p><a href="{{ .Site.Home.RelPermalink }}">&larr; Home</a></p>
  <h1>{{ .Title }}</h1>
  <ul>
    {{ range (where .Site.RegularPages "Section" "tar1090days").ByDate.Reverse }}
    <li><a href="{{ .RelPermalink }}">{{ .Title }}</a></li>
    {{ end }}
  </ul>
</body>
</html>
```

- [ ] **Step 3: Generate the per-day shell from the vendored `index.html`**

`static/tar1090/index.html` has exactly 24 relative asset references (all `href=`/`src=` attributes pointing at local files, none pointing at `http(s)://`). Verify this count hasn't changed before generating, then run the generation script:

Run: `grep -coE '(src|href)="[a-zA-Z][^"]*"' static/tar1090/index.html`
Expected: `24`

Run this Python script (one-time, not committed — do not save it as a file):

```bash
python3 - <<'EOF'
from pathlib import Path

REPLACEMENTS = [
    ('href="libs/jquery-ui-1.13.2.min.css"', 'href="{{ "tar1090/libs/jquery-ui-1.13.2.min.css" | relURL }}"'),
    ('href="libs/ol-8.2.0.css"', 'href="{{ "tar1090/libs/ol-8.2.0.css" | relURL }}"'),
    ('href="libs/ol-layerswitcher-4.1.1.css"', 'href="{{ "tar1090/libs/ol-layerswitcher-4.1.1.css" | relURL }}"'),
    ('href="style.css"', 'href="{{ "tar1090/style.css" | relURL }}"'),
    ('href="images/tar1090-favicon.png"', 'href="{{ "tar1090/images/tar1090-favicon.png" | relURL }}"'),
    ('src="libs/jquery-3.6.1.min.js"', 'src="{{ "tar1090/libs/jquery-3.6.1.min.js" | relURL }}"'),
    ('src="libs/elm-pep-01.js"', 'src="{{ "tar1090/libs/elm-pep-01.js" | relURL }}"'),
    ('src="libs/jquery-ui-1.13.2.min.js"', 'src="{{ "tar1090/libs/jquery-ui-1.13.2.min.js" | relURL }}"'),
    ('src="libs/jquery.ui.touch-punch-1.0.8.js"', 'src="{{ "tar1090/libs/jquery.ui.touch-punch-1.0.8.js" | relURL }}"'),
    ('src="libs/zstddec-tar1090-0.0.5.js"', 'src="{{ "tar1090/libs/zstddec-tar1090-0.0.5.js" | relURL }}"'),
    ('src="libs/ol-custom-10.9.0.js"', 'src="{{ "tar1090/libs/ol-custom-10.9.0.js" | relURL }}"'),
    ('src="early.js"', 'src="{{ "tar1090/early.js" | relURL }}"'),
    ('src="defaults.js"', 'src="{{ "tar1090/defaults.js" | relURL }}"'),
    ('src="config.js"', 'src="{{ "tar1090/config.js" | relURL }}"'),
    ('src="dbloader.js"', 'src="{{ "tar1090/dbloader.js" | relURL }}"'),
    ('src="registrations.js"', 'src="{{ "tar1090/registrations.js" | relURL }}"'),
    ('src="formatter.js"', 'src="{{ "tar1090/formatter.js" | relURL }}"'),
    ('src="flags.js"', 'src="{{ "tar1090/flags.js" | relURL }}"'),
    ('src="layers.js"', 'src="{{ "tar1090/layers.js" | relURL }}"'),
    ('src="geomag2020.js"', 'src="{{ "tar1090/geomag2020.js" | relURL }}"'),
    ('src="markers.js"', 'src="{{ "tar1090/markers.js" | relURL }}"'),
    ('src="planeObject.js"', 'src="{{ "tar1090/planeObject.js" | relURL }}"'),
    ('src="script.js"', 'src="{{ "tar1090/script.js" | relURL }}"'),
    ('href="images/sprites.png"', 'href="{{ "tar1090/images/sprites.png" | relURL }}"'),
]

text = Path("static/tar1090/index.html").read_text()
for old, new in REPLACEMENTS:
    count = text.count(old)
    assert count == 1, f"expected exactly 1 occurrence of {old!r}, found {count}"
    text = text.replace(old, new)

Path("layouts/tar1090days").mkdir(parents=True, exist_ok=True)
Path("layouts/tar1090days/single.html").write_text(text)
print("wrote layouts/tar1090days/single.html")
EOF
```

Expected output: `wrote layouts/tar1090days/single.html` (an `AssertionError` means the vendored `index.html` has drifted from what this plan assumed — stop and re-derive the replacement list from the actual file instead of forcing it).

- [ ] **Step 4: Verify no relative asset references remain unconverted**

Run: `grep -coE '(src|href)="[a-zA-Z][^"]*"' layouts/tar1090days/single.html`
Expected: `0` (all 24 were rewritten to `{{ ... | relURL }}` calls; any raw `src="..."`/`href="..."` left over means a replacement didn't match).

- [ ] **Step 5: Build and verify the section renders with zero day pages**

Run: `hugo --minify`
Expected: exits 0, no errors (no `content/tar1090days/<date>.md` files exist yet at this point in the plan — only `_index.md` — so the list page should render with an empty `<ul>`).

Run: `test -f public/tar1090/days/index.html && echo OK`
Expected: prints `OK`.

- [ ] **Step 6: Commit**

```bash
git add hugo.toml content/tar1090days/_index.md layouts/tar1090days
git commit -m "Add Hugo per-day tar1090 shell and day index page"
```

---

### Task 4: Cross-link from the existing per-day archive page

**Files:**
- Modify: `layouts/days/single.html`

**Interfaces:**
- Consumes: `/tar1090/days/<date>/` existing at build time once Task 2/5 have populated `content/tar1090days/<date>.md` (Task 3's routing).
- Produces: rendered `/days/<date>/` page with a new link, verified by Task 6's build check.

- [ ] **Step 1: Add the link**

In `layouts/days/single.html`, change:

```html
  <p><a href="{{ .Site.Home.RelPermalink }}">&larr; All days</a></p>
  <h1>{{ .Title }}</h1>
```

to:

```html
  <p><a href="{{ .Site.Home.RelPermalink }}">&larr; All days</a></p>
  <h1>{{ .Title }}</h1>
  <p><a href="{{ printf "tar1090/days/%s/" .File.ContentBaseName | relURL }}">View live trace map &rarr;</a></p>
```

- [ ] **Step 2: Build and verify**

Run: `hugo --minify`
Expected: exits 0, no errors.

Run: `grep -o 'View live trace map' public/days/2026-07-22/index.html`
Expected: prints `View live trace map`.

- [ ] **Step 3: Commit**

```bash
git add layouts/days/single.html
git commit -m "Link the tar1090 daily trace map from each per-day archive page"
```

---

### Task 5: Backfill script for pre-existing days

**Files:**
- Create: `scripts/backfill_tar1090_days.py`
- Test: `scripts/tests/test_backfill_tar1090_days.py`

**Interfaces:**
- Consumes: `append_chunk`, `write_receiver_json`, `write_snapshot`, `write_tar1090_day_page` from `scripts.tar1090_feed` (Task 1).
- Produces: `backfill_day(date: str, raw_path: Path, tar1090_days_dir: Path, content_dir: Path) -> None` and `backfill_all(raw_dir: Path, tar1090_days_dir: Path, content_dir: Path, skip_date: str) -> None` — no other task consumes these; it's a standalone manual tool.

- [ ] **Step 1: Write the failing tests**

Create `scripts/tests/test_backfill_tar1090_days.py`:

```python
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


def test_backfill_all_skips_the_given_date(tmp_path):
    raw_dir = tmp_path / "raw"
    _write_raw(raw_dir / "2026-07-22.jsonl", RAW_LINES)
    _write_raw(raw_dir / "2026-07-23.jsonl", RAW_LINES)
    days_dir = tmp_path / "days"
    content_dir = tmp_path / "content"

    backfill_all(raw_dir, days_dir, content_dir, skip_date="2026-07-23")

    assert (days_dir / "2026-07-22").exists()
    assert not (days_dir / "2026-07-23").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=. pytest scripts/tests/test_backfill_tar1090_days.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.backfill_tar1090_days'`.

- [ ] **Step 3: Implement `scripts/backfill_tar1090_days.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=. pytest scripts/tests/test_backfill_tar1090_days.py -v`
Expected: 2 passed.

- [ ] **Step 5: Run the full test suite**

Run: `PYTHONPATH=. pytest scripts/tests -v`
Expected: all tests pass (21 total: 19 from Tasks 1-2 + 2 new).

- [ ] **Step 6: Run the backfill for real**

Run: `PYTHONPATH=. python -m scripts.backfill_tar1090_days`
Expected: exits 0. Since today's date (whatever it is at execution time) is skipped, this populates `static/tar1090/days/<date>/` and `content/tar1090days/<date>.md` for every other day currently in `data/raw/` (at minimum, `2026-07-22.jsonl` — `2026-07-23.jsonl` is skipped if run on 2026-07-23 or later, and will instead be covered once Task 6's live pipeline run processes it, or by a later backfill run after the date has rolled over).

- [ ] **Step 7: Commit**

```bash
git add scripts/backfill_tar1090_days.py scripts/tests/test_backfill_tar1090_days.py static/tar1090/days content/tar1090days
git commit -m "Add tar1090 daily-view backfill script and backfill existing days"
```

---

### Task 6: Workflow, README, and end-to-end verification

**Files:**
- Modify: `.github/workflows/track.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: everything from Tasks 1-5.
- Produces: verified working site (no consumers within this plan).

- [ ] **Step 1: Update `.github/workflows/track.yml`**

Find this line:
```yaml
          git add data/raw data/daily content/days static/tar1090/data static/tar1090/chunks
```
Replace with:
```yaml
          git add data/raw data/daily content/days static/tar1090/data static/tar1090/chunks static/tar1090/days content/tar1090days
```

- [ ] **Step 2: Update `README.md`**

In the numbered pipeline list, change the "Live feed" item:

```markdown
3. **Live feed**: `scripts/tar1090_feed.py` writes a current-position
   snapshot and a rolling 24-hour window of history chunks in
   [readsb](https://github.com/wiedehopf/readsb)'s own JSON format, consumed
   directly by the vendored [tar1090](https://github.com/wiedehopf/tar1090)
   web interface at `/tar1090/` — no server process required, tar1090 is
   pure client-side JS fetching relative JSON files.
```

to:

```markdown
3. **Live feed**: `scripts/tar1090_feed.py` writes a current-position
   snapshot and a rolling 24-hour window of history chunks in
   [readsb](https://github.com/wiedehopf/readsb)'s own JSON format, consumed
   directly by the vendored [tar1090](https://github.com/wiedehopf/tar1090)
   web interface at `/tar1090/` — no server process required, tar1090 is
   pure client-side JS fetching relative JSON files. The same functions
   also write a permanent, unpruned chunk history per UTC day to
   `static/tar1090/days/<date>/`, finalized (aircraft list emptied) once the
   day ends, giving each day a permanent tar1090 trace view at
   `/tar1090/days/<date>/`.
```

In the "Site structure" section, change:

```markdown
- `/tar1090/` — live, rolling 24-hour map view (vendored tar1090, pinned to
  commit `9508b4e1dd2400039b76c971880eebdd89cacc61`; re-vendor manually to
  pick up upstream updates — there's no automatic update mechanism).
```

to:

```markdown
- `/tar1090/` — live, rolling 24-hour map view (vendored tar1090, pinned to
  commit `9508b4e1dd2400039b76c971880eebdd89cacc61`; re-vendor manually to
  pick up upstream updates — there's no automatic update mechanism).
- `/tar1090/days/<date>/` — permanent, per-day tar1090 trace view: the same
  map UI as the live view, scoped to one calendar day's full chunk history
  instead of a trailing 24h window. A thin Hugo-rendered shell
  (`layouts/tar1090days/single.html`) reuses the shared vendored assets, so
  each day only adds a small `data/`+`chunks/` JSON folder, not a copy of
  tar1090 itself. `/tar1090/days/` lists all days.
```

In the "Repo layout" section, change:

```markdown
scripts/               Python data pipeline (poll, aggregate, tar1090 feed, tests)
data/raw/               Raw per-poll sightings, one JSONL file per UTC day
data/daily/             Aggregated per-day flight tracks (JSON)
content/days/           Generated Hugo content pages, one per day
layouts/                Hugo templates (homepage, day page)
static/js/map.js        Leaflet map rendering for the daily archive pages
static/tar1090/         Vendored tar1090 live-view web interface
static/tar1090/data/    Generated current-snapshot feed (aircraft.json, receiver.json)
static/tar1090/chunks/  Generated rolling 24h history chunks
.github/workflows/      The poll → build → deploy workflow
```

to:

```markdown
scripts/               Python data pipeline (poll, aggregate, tar1090 feed, backfill, tests)
data/raw/               Raw per-poll sightings, one JSONL file per UTC day
data/daily/             Aggregated per-day flight tracks (JSON)
content/days/           Generated Hugo content pages, one per day
content/tar1090days/    Generated Hugo content pages for tar1090 daily views, one per day
layouts/                Hugo templates (homepage, day page, tar1090 daily shell/index)
static/js/map.js        Leaflet map rendering for the daily archive pages
static/tar1090/         Vendored tar1090 live-view web interface
static/tar1090/data/    Generated current-snapshot feed (aircraft.json, receiver.json)
static/tar1090/chunks/  Generated rolling 24h history chunks
static/tar1090/days/    Generated permanent per-day chunk history (one folder per UTC day)
.github/workflows/      The poll → build → deploy workflow
```

- [ ] **Step 3: Run the full Python test suite**

Run: `PYTHONPATH=. pytest scripts/tests -v`
Expected: all tests pass (21 total).

- [ ] **Step 4: Run the pipeline for real once, to write today's day view**

Run: `PYTHONPATH=. python -m scripts.run`
Expected: exits 0. Writes/updates today's `static/tar1090/days/<today>/` and `content/tar1090days/<today>.md`, in addition to the existing rolling-view and archive outputs.

- [ ] **Step 5: Build and verify**

Run: `hugo --minify`
Expected: exits 0, no errors.

Run: `test -f public/tar1090/days/index.html && echo OK`
Expected: prints `OK`.

Run: `ls public/tar1090/days/ | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'`
Expected: prints at least one date directory (2026-07-22, from Task 5's backfill, plus today's date from Step 4 above).

Run: `test -f public/tar1090/days/2026-07-22/index.html && echo OK`
Expected: prints `OK`.

Run: `test -f public/tar1090/days/2026-07-22/data/aircraft.json && echo OK`
Expected: prints `OK`.

Run: `grep -o 'View live trace map' public/days/2026-07-22/index.html`
Expected: prints `View live trace map`.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/track.yml README.md data/raw data/daily content/days content/tar1090days static/tar1090/data static/tar1090/chunks static/tar1090/days
git commit -m "Document per-day tar1090 views, wire workflow paths, seed today's data"
```

---

## Self-Review Notes

- **Spec coverage:** output layout with shared assets + thin shells (Task 3), no chunk pruning within a day / `retain=400` safety ceiling (Task 2's `append_chunk` call), stateless idempotent day-rollover finalization (Task 1 `finalize_other_days` + Task 2 wiring + Task 2's rollover test), backfill for pre-existing days (Task 5), cross-links from `/days/<date>/` and a `/tar1090/days/` index (Task 3 Step 2, Task 4), no vendored-file modifications (Task 3 builds the shell from a generation script into a new `layouts/` file, never touching `static/tar1090/*`), workflow `git add` paths and README updates (Task 6), "all days forever" retention (no pruning logic anywhere in this plan).
- **Placeholder scan:** no TBD/TODO; every step has complete, runnable code or exact shell commands with expected output.
- **Type consistency:** `main()`'s new signature (`raw_dir, daily_dir, content_dir, tar1090_data_dir, tar1090_chunks_dir, tar1090_days_dir, tar1090_days_content_dir, now=None`) matches across Task 2's test calls, implementation, and `__main__` block. `write_tar1090_day_page(date, content_dir)` and `finalize_other_days(days_root, today, now_epoch_s)` signatures match between Task 1's tests/implementation and Task 2/5's call sites. `backfill_day(date, raw_path, tar1090_days_dir, content_dir)` and `backfill_all(raw_dir, tar1090_days_dir, content_dir, skip_date)` match between Task 5's tests, implementation, and `__main__` block.
