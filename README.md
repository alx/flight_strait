# Trabzon Overflight Tracker

A Hugo static site that publishes one page per day of long-haul flights
observed passing near Trabzon, Turkey — a node on the Black Sea / Caucasus
overflight corridor used by Europe–Gulf and Europe–Asia traffic. Data comes
from the free [`api.adsb.lol`](https://api.adsb.lol) ADS-B aggregation API.

Live site: https://alx.github.io/flight_strait/

## How it works

A GitHub Actions workflow (`.github/workflows/track.yml`) runs every 5
minutes, all day:

1. **Poll**: `scripts/poll.py` queries `api.adsb.lol` for aircraft within
   150nm of Trabzon (40.995°N, 39.789°E) and appends the raw response as one
   JSON line to `data/raw/<UTC-date>.jsonl` (permanent, append-only).
2. **Aggregate**: `scripts/aggregate.py` reads the day's raw sightings,
   groups them into one track per aircraft (by ICAO hex + callsign), and
   computes first/last-seen times, min/max altitude, and closest-approach
   distance to Trabzon. Writes `data/daily/<UTC-date>.json` (overwritten on
   every poll) and `content/days/<UTC-date>.md`.
3. **Commit**: pushes the updated data and content files.
4. **Build & deploy**: `hugo --minify` builds the site, which is deployed to
   GitHub Pages.

The day-boundary and all timestamps use UTC throughout.

## Site structure

- `/` — archive of all days, reverse chronological.
- `/days/<date>/` — per-day table (callsign, hex, registration, type,
  first/last seen, altitude, closest approach to Trabzon) plus a Leaflet map
  showing the query radius, the Trabzon reference point, and each flight's
  track.

No flight origin/destination data is shown — `api.adsb.lol` doesn't provide
it, so the site only reports observed position, altitude, and timing.

## Development

```bash
# Python pipeline
pip install -r scripts/requirements.txt
PYTHONPATH=. pytest scripts/tests -v   # run tests
PYTHONPATH=. python -m scripts.run     # poll once, aggregate, write files

# Hugo site
hugo --minify   # build to public/
hugo server     # local preview with live reload
```

## Repo layout

```
scripts/          Python data pipeline (poll, aggregate, tests)
data/raw/          Raw per-poll sightings, one JSONL file per UTC day
data/daily/        Aggregated per-day flight tracks (JSON)
content/days/      Generated Hugo content pages, one per day
layouts/           Hugo templates (homepage, day page)
static/js/map.js   Leaflet map rendering
.github/workflows/ The poll → build → deploy workflow
```
