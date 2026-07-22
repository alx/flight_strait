# Caspian Corridor Daily Flight Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Hugo static site that shows one page per day of long-haul flights observed crossing the Caspian Sea corridor between Baku and Turkmenbashi, fed by a GitHub Actions workflow that polls `api.adsb.lol` every 5 minutes and redeploys.

**Architecture:** Python scripts poll `api.adsb.lol`, append raw sightings to per-day JSONL files, aggregate them into per-flight track summaries (closest-approach distance to two reference points), and write both a Hugo data file and a Hugo content page. Hugo renders a table + Leaflet map per day and an archive homepage. A single GitHub Actions workflow runs the whole pipeline and deploys to GitHub Pages.

**Tech Stack:** Hugo (static site), Python 3 + `requests` (data pipeline), pytest (tests), Leaflet via CDN (map), GitHub Actions + GitHub Pages (build/deploy).

## Global Constraints

- Query endpoint: `https://api.adsb.lol/v2/point/40.27/51.53/150` (center ~40.27°N, 51.53°E, radius 150nm).
- Reference points (airport coordinates, not verified VOR fixes): Baku GYD = 40.4675°N, 50.0467°E; Turkmenbashi KRW = 40.0633°N, 53.0072°E.
- Day boundary is UTC calendar date, used consistently for raw file names, daily aggregates, and content pages.
- No flight origin/destination data — out of scope per spec.
- Poll cadence: every 5 minutes, all day, via GitHub Actions cron `*/5 * * * *`.
- Raw per-poll sightings are permanent/append-only; daily aggregate JSON is recomputed (overwritten) on every poll.

---

### Task 1: Hugo site scaffolding

**Files:**
- Create: `hugo.toml`
- Create: `.gitignore`
- Create: `data/raw/.gitkeep`
- Create: `data/daily/.gitkeep`

**Interfaces:**
- Produces: Hugo site root with `hugo.toml`, `content/`, `layouts/`, `static/`, `data/raw/`, `data/daily/` directories that later tasks write into.

- [ ] **Step 1: Verify Hugo is installed**

Run: `hugo version`
Expected: prints a version string (e.g. `hugo v0.13x.x`). If it fails, install Hugo for your OS (e.g. `brew install hugo` on macOS, `sudo apt install hugo` on Debian/Ubuntu) before continuing.

- [ ] **Step 2: Scaffold the site**

Run: `hugo new site . --force`
Expected: creates `archetypes/`, `content/`, `layouts/`, `static/`, `themes/`, and a `hugo.toml` in the current directory (the existing `.git` and `docs/` are left alone since `--force` only skips the "directory not empty" check).

- [ ] **Step 3: Configure `hugo.toml`**

```toml
baseURL = "https://example.github.io/flight_strait/"
languageCode = "en-us"
title = "Caspian Corridor Flight Tracker"

[params]
  bakuLat = 40.4675
  bakuLon = 50.0467
  turkmenbashiLat = 40.0633
  turkmenbashiLon = 53.0072
  queryLat = 40.27
  queryLon = 51.53
  queryRadiusNm = 150
```

- [ ] **Step 4: Add `.gitignore`**

```
public/
resources/
.hugo_build.lock
__pycache__/
*.pyc
```

- [ ] **Step 5: Create data directories with placeholders**

Run:
```bash
mkdir -p data/raw data/daily
touch data/raw/.gitkeep data/daily/.gitkeep
```

- [ ] **Step 6: Verify the site builds**

Run: `hugo --minify`
Expected: exits 0, prints a build summary, and creates `public/index.html`.

- [ ] **Step 7: Commit**

```bash
git add hugo.toml .gitignore archetypes content layouts static data/raw/.gitkeep data/daily/.gitkeep
git commit -m "Scaffold Hugo site"
```

---

### Task 2: Geo distance utility

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/geo.py`
- Create: `scripts/requirements.txt`
- Test: `scripts/tests/__init__.py`
- Test: `scripts/tests/test_geo.py`

**Interfaces:**
- Produces: `haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float` — great-circle distance in nautical miles, used by Task 3's aggregation logic.

- [ ] **Step 1: Create package files and requirements**

`scripts/__init__.py` (empty file).

`scripts/tests/__init__.py` (empty file).

`scripts/requirements.txt`:
```
requests==2.32.3
pytest==8.3.3
```

- [ ] **Step 2: Write the failing test**

`scripts/tests/test_geo.py`:
```python
from scripts.geo import haversine_nm


def test_same_point_is_zero_distance():
    assert haversine_nm(40.4675, 50.0467, 40.4675, 50.0467) == 0.0


def test_baku_to_turkmenbashi_is_about_127_nm():
    # Known-good reference distance between the two airports, used to
    # sanity-check the formula rather than assert an exact float.
    distance = haversine_nm(40.4675, 50.0467, 40.0633, 53.0072)
    assert 120 < distance < 135
```

- [ ] **Step 3: Run test to verify it fails**

Run: `PYTHONPATH=. pytest scripts/tests/test_geo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.geo'`

- [ ] **Step 4: Implement `haversine_nm`**

`scripts/geo.py`:
```python
import math

EARTH_RADIUS_NM = 3440.065


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in nautical miles."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_NM * c
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=. pytest scripts/tests/test_geo.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add scripts/__init__.py scripts/geo.py scripts/requirements.txt scripts/tests/__init__.py scripts/tests/test_geo.py
git commit -m "Add haversine distance utility"
```

---

### Task 3: Daily aggregation logic

**Files:**
- Create: `scripts/aggregate.py`
- Test: `scripts/tests/test_aggregate.py`

**Interfaces:**
- Consumes: `haversine_nm(lat1, lon1, lat2, lon2) -> float` from `scripts.geo` (Task 2).
- Produces:
  - `aggregate_day(raw_lines: list[dict], date: str) -> dict` — returns the daily JSON structure (see Step 4) consumed by Task 5 (`run.py`) and by Hugo templates (Task 6) once written to `data/daily/<date>.json`.
  - `write_content_page(date: str, flight_count: int, content_dir: pathlib.Path) -> None` — (over)writes `content_dir/<date>.md`, consumed by Task 5.

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_aggregate.py`:
```python
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
    assert flight["closest_baku_nm"] > 0
    assert flight["closest_turkmenbashi_nm"] > 0


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest scripts/tests/test_aggregate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.aggregate'`

- [ ] **Step 3: Implement `scripts/aggregate.py`**

```python
from pathlib import Path

from scripts.geo import haversine_nm

BAKU = (40.4675, 50.0467)
TURKMENBASHI = (40.0633, 53.0072)


def aggregate_day(raw_lines: list[dict], date: str) -> dict:
    tracks: dict[tuple[str, str], dict] = {}

    for line in raw_lines:
        poll_time = line["poll_time"]
        for ac in line["aircraft"]:
            lat, lon = ac.get("lat"), ac.get("lon")
            if lat is None or lon is None:
                continue

            flight_id = ac.get("flight", "").strip()
            key = (ac["hex"], flight_id)

            track = tracks.setdefault(
                key,
                {
                    "hex": ac["hex"],
                    "flight": flight_id,
                    "registration": ac.get("r"),
                    "type": ac.get("t"),
                    "first_seen": poll_time,
                    "last_seen": poll_time,
                    "alt_min": ac.get("alt_baro"),
                    "alt_max": ac.get("alt_baro"),
                    "track": [],
                    "closest_baku_nm": None,
                    "closest_turkmenbashi_nm": None,
                },
            )

            track["first_seen"] = min(track["first_seen"], poll_time)
            track["last_seen"] = max(track["last_seen"], poll_time)

            alt = ac.get("alt_baro")
            if isinstance(alt, (int, float)):
                track["alt_min"] = alt if track["alt_min"] is None else min(track["alt_min"], alt)
                track["alt_max"] = alt if track["alt_max"] is None else max(track["alt_max"], alt)

            track["track"].append(
                {
                    "time": poll_time,
                    "lat": lat,
                    "lon": lon,
                    "alt": alt,
                    "track": ac.get("track"),
                    "gs": ac.get("gs"),
                }
            )

            dist_baku = haversine_nm(lat, lon, *BAKU)
            dist_turkmenbashi = haversine_nm(lat, lon, *TURKMENBASHI)

            if track["closest_baku_nm"] is None or dist_baku < track["closest_baku_nm"]:
                track["closest_baku_nm"] = round(dist_baku, 1)
            if (
                track["closest_turkmenbashi_nm"] is None
                or dist_turkmenbashi < track["closest_turkmenbashi_nm"]
            ):
                track["closest_turkmenbashi_nm"] = round(dist_turkmenbashi, 1)

    flights = sorted(tracks.values(), key=lambda t: t["first_seen"])
    return {"date": date, "flights": flights}


def write_content_page(date: str, flight_count: int, content_dir: Path) -> None:
    content_dir.mkdir(parents=True, exist_ok=True)
    page_path = content_dir / f"{date}.md"
    page_path.write_text(
        f'---\ntitle: "{date}"\ndate: {date}T00:00:00Z\nflight_count: {flight_count}\n---\n'
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest scripts/tests/test_aggregate.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/aggregate.py scripts/tests/test_aggregate.py
git commit -m "Add daily aggregation logic"
```

---

### Task 4: API polling

**Files:**
- Create: `scripts/poll.py`
- Test: `scripts/tests/test_poll.py`

**Interfaces:**
- Produces:
  - `poll_once() -> dict` — calls the adsb.lol endpoint and returns the parsed JSON response (`{"ac": [...], "now": ..., ...}`), consumed by Task 5.
  - `append_sighting(raw_path: pathlib.Path, poll_time: str, response: dict) -> None` — appends one JSON line `{"poll_time": ..., "aircraft": [...]}` to `raw_path`, consumed by Task 5.

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_poll.py`:
```python
import json
from unittest.mock import Mock, patch

from scripts.poll import append_sighting, poll_once

FAKE_RESPONSE = {
    "ac": [{"hex": "abc123", "flight": "UAL123", "lat": 40.2, "lon": 51.0}],
    "now": 1753171200000,
    "total": 1,
    "msg": "No error",
}


@patch("scripts.poll.requests.get")
def test_poll_once_calls_expected_url_and_returns_json(mock_get):
    mock_get.return_value = Mock(status_code=200, json=lambda: FAKE_RESPONSE)

    result = poll_once()

    mock_get.assert_called_once_with(
        "https://api.adsb.lol/v2/point/40.27/51.53/150", timeout=10
    )
    assert result == FAKE_RESPONSE


def test_append_sighting_writes_one_json_line(tmp_path):
    raw_path = tmp_path / "2026-07-22.jsonl"

    append_sighting(raw_path, "2026-07-22T10:00:00Z", FAKE_RESPONSE)
    append_sighting(raw_path, "2026-07-22T10:05:00Z", FAKE_RESPONSE)

    lines = raw_path.read_text().splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first["poll_time"] == "2026-07-22T10:00:00Z"
    assert first["aircraft"] == FAKE_RESPONSE["ac"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest scripts/tests/test_poll.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.poll'`

- [ ] **Step 3: Implement `scripts/poll.py`**

```python
import json
from pathlib import Path

import requests

QUERY_URL = "https://api.adsb.lol/v2/point/40.27/51.53/150"


def poll_once() -> dict:
    response = requests.get(QUERY_URL, timeout=10)
    return response.json()


def append_sighting(raw_path: Path, poll_time: str, response: dict) -> None:
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"poll_time": poll_time, "aircraft": response.get("ac", [])})
    with raw_path.open("a") as f:
        f.write(line + "\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest scripts/tests/test_poll.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/poll.py scripts/tests/test_poll.py
git commit -m "Add adsb.lol polling"
```

---

### Task 5: Pipeline orchestration entry point

**Files:**
- Create: `scripts/run.py`
- Test: `scripts/tests/test_run.py`

**Interfaces:**
- Consumes:
  - `poll_once() -> dict` and `append_sighting(raw_path, poll_time, response)` from `scripts.poll` (Task 4).
  - `aggregate_day(raw_lines, date) -> dict` and `write_content_page(date, flight_count, content_dir)` from `scripts.aggregate` (Task 3).
- Produces: `main(raw_dir: Path, daily_dir: Path, content_dir: Path, now=None) -> None` — the single function the GitHub Actions workflow (Task 7) invokes via `python -m scripts.run`.

- [ ] **Step 1: Write the failing test**

`scripts/tests/test_run.py`:
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


@patch("scripts.run.poll_once", return_value=FAKE_RESPONSE)
def test_main_writes_raw_daily_and_content_files(mock_poll, tmp_path):
    raw_dir = tmp_path / "data" / "raw"
    daily_dir = tmp_path / "data" / "daily"
    content_dir = tmp_path / "content" / "days"
    fixed_now = datetime(2026, 7, 22, 10, 0, 0, tzinfo=timezone.utc)

    main(raw_dir, daily_dir, content_dir, now=fixed_now)

    raw_file = raw_dir / "2026-07-22.jsonl"
    assert raw_file.exists()
    assert json.loads(raw_file.read_text().splitlines()[0])["aircraft"] == FAKE_RESPONSE["ac"]

    daily_file = daily_dir / "2026-07-22.json"
    daily_data = json.loads(daily_file.read_text())
    assert daily_data["date"] == "2026-07-22"
    assert len(daily_data["flights"]) == 1

    content_file = content_dir / "2026-07-22.md"
    assert "flight_count: 1" in content_file.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest scripts/tests/test_run.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.run'`

- [ ] **Step 3: Implement `scripts/run.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest scripts/tests/test_run.py -v`
Expected: 1 passed

- [ ] **Step 5: Run the full test suite**

Run: `PYTHONPATH=. pytest scripts/tests -v`
Expected: all tests from Tasks 2-5 pass (9 tests total)

- [ ] **Step 6: Commit**

```bash
git add scripts/run.py scripts/tests/test_run.py
git commit -m "Add pipeline orchestration entry point"
```

---

### Task 6: Hugo templates (homepage, day page, map)

**Files:**
- Create: `layouts/index.html`
- Create: `layouts/days/single.html`
- Create: `static/js/map.js`

**Interfaces:**
- Consumes: `data/daily/<date>.json` shape from Task 3 (`{"date": ..., "flights": [{"hex", "flight", "registration", "type", "first_seen", "last_seen", "alt_min", "alt_max", "track": [...], "closest_baku_nm", "closest_turkmenbashi_nm"}]}`); `content/days/<date>.md` front matter (`title`, `date`, `flight_count`) from Task 3.
- Produces: rendered `public/index.html` and `public/days/<date>/index.html`, verified by grepping build output (no consumers within this plan).

- [ ] **Step 1: Create a fixture day to render against**

Run:
```bash
mkdir -p data/daily content/days
cat > data/daily/2026-07-22.json <<'EOF'
{
  "date": "2026-07-22",
  "flights": [
    {
      "hex": "abc123",
      "flight": "UAL123",
      "registration": "N12345",
      "type": "B789",
      "first_seen": "2026-07-22T10:00:00Z",
      "last_seen": "2026-07-22T10:20:00Z",
      "alt_min": 35000,
      "alt_max": 36000,
      "track": [
        {"time": "2026-07-22T10:00:00Z", "lat": 40.2, "lon": 51.0, "alt": 35000, "track": 90, "gs": 480},
        {"time": "2026-07-22T10:20:00Z", "lat": 40.3, "lon": 51.8, "alt": 36000, "track": 91, "gs": 481}
      ],
      "closest_baku_nm": 45.2,
      "closest_turkmenbashi_nm": 60.1
    }
  ]
}
EOF
cat > content/days/2026-07-22.md <<'EOF'
---
title: "2026-07-22"
date: 2026-07-22T00:00:00Z
flight_count: 1
---
EOF
```

- [ ] **Step 2: Write the homepage template**

`layouts/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ .Site.Title }}</title>
</head>
<body>
  <h1>{{ .Site.Title }}</h1>
  <ul>
    {{ range (where .Site.RegularPages "Section" "days").ByDate.Reverse }}
    <li>
      <a href="{{ .RelPermalink }}">{{ .Title }}</a>
      &mdash; {{ .Params.flight_count }} flight(s)
    </li>
    {{ end }}
  </ul>
</body>
</html>
```

- [ ] **Step 3: Write the day-page template**

`layouts/days/single.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ .Title }} &mdash; {{ .Site.Title }}</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
</head>
<body>
  <p><a href="{{ "/" | relURL }}">&larr; All days</a></p>
  <h1>{{ .Title }}</h1>

  {{ $date := .File.ContentBaseName }}
  {{ $day := index .Site.Data.daily $date }}

  <table border="1" cellpadding="4">
    <thead>
      <tr>
        <th>Callsign</th><th>Hex</th><th>Registration</th><th>Type</th>
        <th>First seen (UTC)</th><th>Last seen (UTC)</th>
        <th>Alt min/max (ft)</th>
        <th>Closest to Baku (nm)</th><th>Closest to Turkmenbashi (nm)</th>
      </tr>
    </thead>
    <tbody>
      {{ range $day.flights }}
      <tr>
        <td>{{ .flight }}</td>
        <td>{{ .hex }}</td>
        <td>{{ .registration }}</td>
        <td>{{ .type }}</td>
        <td>{{ .first_seen }}</td>
        <td>{{ .last_seen }}</td>
        <td>{{ .alt_min }} / {{ .alt_max }}</td>
        <td>{{ .closest_baku_nm }}</td>
        <td>{{ .closest_turkmenbashi_nm }}</td>
      </tr>
      {{ end }}
    </tbody>
  </table>

  <div id="map" style="height: 500px;"></div>

  <script type="application/json" id="flight-data">{{ $day | jsonify }}</script>
  <script>
    window.CASPIAN_REFERENCE_POINTS = {
      baku: [{{ .Site.Params.bakuLat }}, {{ .Site.Params.bakuLon }}],
      turkmenbashi: [{{ .Site.Params.turkmenbashiLat }}, {{ .Site.Params.turkmenbashiLon }}]
    };
  </script>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="{{ "js/map.js" | relURL }}"></script>
</body>
</html>
```

- [ ] **Step 4: Write the map script**

`static/js/map.js`:
```javascript
(function () {
  var data = JSON.parse(document.getElementById("flight-data").textContent);
  var refs = window.CASPIAN_REFERENCE_POINTS;

  var map = L.map("map").setView([refs.baku[0], (refs.baku[1] + refs.turkmenbashi[1]) / 2], 6);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  L.marker(refs.baku).addTo(map).bindPopup("Baku");
  L.marker(refs.turkmenbashi).addTo(map).bindPopup("Turkmenbashi");

  var colors = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#46f0f0"];

  (data.flights || []).forEach(function (flight, i) {
    var points = flight.track.map(function (p) {
      return [p.lat, p.lon];
    });
    L.polyline(points, { color: colors[i % colors.length] })
      .addTo(map)
      .bindPopup(flight.flight || flight.hex);
  });
})();
```

- [ ] **Step 5: Build and verify rendered output**

Run: `hugo --minify`
Expected: exits 0.

Run: `grep -o 'UAL123' public/days/2026-07-22/index.html`
Expected: prints `UAL123` (confirms the table rendered flight data from the fixture).

Run: `grep -o '"flight-data"' public/days/2026-07-22/index.html`
Expected: prints `"flight-data"` (confirms the map data script tag rendered).

Run: `grep -o '2026-07-22' public/index.html`
Expected: prints `2026-07-22` (confirms the homepage lists the day).

- [ ] **Step 6: Commit**

```bash
git add layouts/index.html layouts/days/single.html static/js/map.js data/daily/2026-07-22.json content/days/2026-07-22.md
git commit -m "Add Hugo templates for homepage and day pages"
```

---

### Task 7: GitHub Actions pipeline workflow

**Files:**
- Create: `.github/workflows/track.yml`

**Interfaces:**
- Consumes: `scripts/requirements.txt` (Task 2), `python -m scripts.run` entry point (Task 5), `hugo --minify` (Task 1/6).
- Produces: deployed site on GitHub Pages (no consumers within this plan).

- [ ] **Step 1: Write the workflow file**

`.github/workflows/track.yml`:
```yaml
name: Track flights and deploy

on:
  schedule:
    - cron: "*/5 * * * *"
  workflow_dispatch: {}

permissions:
  contents: write
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Python dependencies
        run: pip install -r scripts/requirements.txt

      - name: Poll and aggregate
        run: PYTHONPATH=. python -m scripts.run

      - name: Commit updated data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/raw data/daily content/days
          git diff --cached --quiet || git commit -m "Update flight data $(date -u +%Y-%m-%dT%H:%M:%SZ)"
          git push

      - name: Set up Hugo
        uses: peaceiris/actions-hugo@v3
        with:
          hugo-version: "0.132.0"

      - name: Build site
        run: hugo --minify

      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: public

      - name: Deploy to GitHub Pages
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Validate workflow YAML syntax**

Run: `python3 -c "import yaml, sys; yaml.safe_load(open('.github/workflows/track.yml')); print('valid')"`
Expected: prints `valid` (if `pyyaml` is not installed, run `pip install pyyaml` first — it's a one-off syntax check, not a project dependency).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/track.yml
git commit -m "Add GitHub Actions workflow to poll, aggregate, build, and deploy"
```

- [ ] **Step 4: Manual one-time repo setup (cannot be automated from the workflow file)**

After pushing this branch to GitHub:
1. Go to the repo's Settings → Pages.
2. Under "Build and deployment" → "Source", select "GitHub Actions".
3. Update `baseURL` in `hugo.toml` (Task 1) to match the actual `https://<user>.github.io/<repo>/` URL, commit, and push.
4. Confirm the workflow runs successfully from the Actions tab (it can also be triggered manually via `workflow_dispatch` instead of waiting for the next 5-minute cron tick).

---

## Self-Review Notes

- **Spec coverage:** query/radius (Task 1 config + Task 4), raw JSONL append-only storage (Task 4/5), daily aggregation with closest-approach distances (Task 3), content page + archive homepage (Task 3/6), table + Leaflet map (Task 6), 5-minute GitHub Actions cron with commit+build+deploy (Task 7), UTC day boundary (used consistently in Task 5's `main()` and Task 3/4 tests), no origin/destination (never introduced), reference points as airport coordinates not VOR fixes (Task 1 constants + Task 3 constants match spec).
- **Placeholder scan:** no TBD/TODO; every step has complete, runnable code.
- **Type consistency:** `aggregate_day(raw_lines, date) -> dict` (Task 3) matches its usage in `run.py` (Task 5) and the JSON shape consumed by `layouts/days/single.html` (Task 6). `write_content_page(date, flight_count, content_dir)` signature matches its Task 3 test and its Task 5 call site. `poll_once()` and `append_sighting(raw_path, poll_time, response)` signatures match between Task 4's tests/implementation and Task 5's usage.
