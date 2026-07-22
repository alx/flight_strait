# Caspian Corridor Daily Flight Tracker — Design

## Overview

A Hugo static site that publishes one page per day showing long-haul flights
observed crossing the Caspian Sea corridor between Baku, Azerbaijan and
Turkmenbashi, Turkmenistan. Data comes from the free `api.adsb.lol` ADS-B
aggregation API. A GitHub Actions workflow polls the API every 5 minutes,
appends raw sightings, aggregates them into per-flight tracks, and rebuilds
and redeploys the site to GitHub Pages — so the current day's page updates
throughout the day and every past day remains in a permanent archive.

## Geographic scope

- Query center: ~40.27°N, 51.53°E (midpoint of the corridor), radius 150nm.
  This comfortably covers both shores in a single `api.adsb.lol` point query
  (the API supports point+radius only, up to 250nm — there is no bounding-box
  endpoint).
- Two **route reference points** used only to compute each flight's
  closest-approach distance:
  - Baku (Heydar Aliyev Intl, GYD): 40.4675°N, 50.0467°E
  - Turkmenbashi (KRW): 40.0633°N, 53.0072°E
  - These are airport coordinates, not verified VOR navaid fixes — the design
    intentionally avoids claiming specific VOR identifiers/frequencies since
    that data could not be verified from available sources.
- `api.adsb.lol` does not provide flight origin/destination or route data,
  so the site does not attempt to show or guess routes — only observed
  position, altitude, and timing per aircraft.

## Data pipeline

Single GitHub Actions workflow (`.github/workflows/track.yml`), scheduled
`*/5 * * * *` (every 5 minutes, all day):

1. Checkout repo.
2. **Poll**: Python script calls
   `https://api.adsb.lol/v2/point/40.27/51.53/150`, appends the raw response
   (poll timestamp + full aircraft list) as one JSON line to
   `data/raw/<UTC-date>.jsonl`.
3. **Aggregate**: Python script reads all of today's (UTC) raw sightings and
   groups them by `hex`+`flight` into one track per aircraft, computing:
   - first-seen / last-seen timestamps (UTC)
   - min/max barometric altitude
   - ordered list of `{time, lat, lon, alt, track, gs}` points for map plotting
   - closest-approach distance (haversine) to Baku and to Turkmenbashi
   Writes/overwrites `data/daily/<UTC-date>.json` with this aggregate.
   Creates `content/days/<UTC-date>.md` (minimal front matter: date) the
   first time a new day's data appears.
4. **Commit**: commit and push the updated `data/` and `content/` files
   (bot commit), so raw sightings remain a permanent, append-only audit
   trail and the aggregate reflects the latest poll.
5. **Build**: `hugo --minify`.
6. **Deploy**: publish `public/` to GitHub Pages via
   `actions/deploy-pages` (requires one-time manual repo setting: Pages
   source = "GitHub Actions").

Data grouping uses the UTC calendar date throughout (poll bucketing, day
pages, archive) to avoid timezone/DST complexity.

## Hugo site structure

- `content/days/<date>.md` — one page per day, created by the pipeline.
- `content/days/_index.md` — reverse-chronological archive list of all days
  (date + flight count), linking to each day's page.
- Homepage redirects to / shows the latest day.
- `data/daily/<date>.json` — per-day aggregate, read via Hugo's site data
  access in the day-page template.
- `layouts/days/single.html` — custom template (no third-party theme, since
  the content model is data-driven and unusual):
  - **Table**: callsign, ICAO hex, registration, aircraft type, first-seen,
    last-seen (UTC), min/max altitude, closest-approach distance to Baku,
    closest-approach distance to Turkmenbashi.
  - **Map**: Leaflet (loaded via CDN, no build-time JS dependency) showing
    the search radius circle, the two reference points, and each flight's
    plotted track points, color-coded per flight, sourced from the same
    daily JSON.

## Out of scope

- Flight origin/destination or route information (not available from
  `api.adsb.lol`; a separate route-lookup service was considered and
  rejected to keep the dependency surface minimal).
- Live/real-time in-browser polling (the site is fully static; "live" feel
  comes from redeploying every 5 minutes, not client-side fetches).
- Verified VOR navaid identifiers/frequencies (airport coordinates are used
  as reference points instead).
