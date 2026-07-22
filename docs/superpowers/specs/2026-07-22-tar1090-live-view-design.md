# tar1090 Live View — Design

## Overview

Add a live, rolling-24-hour map view of traffic near Trabzon using
[tar1090](https://github.com/wiedehopf/tar1090), the standard readsb/dump1090-fa
web interface. tar1090 is pure client-side JS/HTML/CSS that fetches relative
JSON endpoints for its data — no server process required — so it can be
vendored into this Hugo static site and hosted on GitHub Pages exactly like
the rest of the project.

This is purely additive. The existing per-day archive (raw JSONL → daily
JSON → Hugo table/map pages) is untouched. The homepage gains a "Live view"
link to the new `/tar1090/` page.

## Why not a full per-date archive in tar1090

tar1090 has two distinct history mechanisms, examined directly in its
source (`html/early.js`, `html/script.js`):

1. **Rolling chunk history** (`chunks/chunk_<ts>.json` + `chunks/chunks.json`
   index) — a trailing window of recent snapshots, refreshed continuously.
   This is what this design uses.
2. **True per-date replay** (`globe_history/<date>/heatmap/*.bin.ttf`) —
   calendar-indexed browsing, but requires the companion `graphs1090` tool
   and a binary heatmap format tied to a persistently-running readsb
   receiver's own history storage. Not feasible to fake from a third-party
   API poll without reverse-engineering a binary format for uncertain
   benefit.

So tar1090 provides a rolling "last ~24 hours" live view, not a permanent
per-day archive — the existing custom Hugo pages remain the permanent
archive.

## Data pipeline extension

New module `scripts/tar1090_feed.py`, consumed by `scripts/run.py`
immediately after `poll_once()` (reuses the same API response — no extra
network calls).

adsb.lol's `ac` array already uses readsb's own aircraft field schema (hex,
flight, lat, lon, alt_baro, gs, track, r, t, ...) since adsb.lol runs on
readsb — aircraft entries pass through unchanged, no remapping needed.
adsb.lol's `now` field is epoch **milliseconds**; tar1090 expects `now` in
epoch **seconds** in JSON bodies, but epoch **milliseconds** in chunk
*filenames* (confirmed from tar1090's own parsing code) — the two are
handled with distinct conversions.

### `write_snapshot(ac_list, now_epoch_s, data_dir) -> None`

Writes `static/tar1090/data/aircraft.json`:

```json
{"now": 1753171200.0, "messages": 0, "aircraft": [ /* ac entries verbatim */ ]}
```

Overwritten on every poll — this is tar1090's "current position" feed,
fetched by its normal refresh loop.

### `append_chunk(ac_list, now_epoch_s, chunks_dir, retain=289) -> None`

Writes `chunks/chunk_<now_epoch_ms>.json` (same snapshot shape as above),
then rewrites `chunks/chunks.json` as `{"chunks": [<oldest ... newest>]}`
and deletes any chunk files that fall outside the last `retain` entries.

`retain=289` = 288 five-minute polls (24h) + 1 safety margin, matching the
existing 5-minute cron cadence.

### `write_receiver_json(data_dir) -> None`

Idempotent; only needs to run once but is safe to call every poll. Writes
`static/tar1090/data/receiver.json`:

```json
{"lat": 40.995, "lon": 39.789, "version": "adsb.lol-poller"}
```

tar1090 reads `lat`/`lon` from this file to center the map and place the
site marker. All other receiver.json fields it looks for are read behind
`if (receiverJson.x)` guards, so a minimal file is safe.

### Wiring

`scripts/run.py`'s `main()` calls `write_snapshot`, `append_chunk`, and
`write_receiver_json` after the existing raw/aggregate/content-page steps,
using the same `now`/`raw poll response` already in scope.

`.github/workflows/track.yml`'s "Commit updated data" step's `git add` gets
`static/tar1090/data static/tar1090/chunks` added alongside the existing
`data/raw data/daily content/days`.

## Static assets & UI integration

- Vendor tar1090's `html/` directory (script.js, index.html, style.css,
  `libs/`, `flags/`, `images/`, `geojson/`, etc. — no build step, plain
  static files) into `static/tar1090/`, committed directly into this repo.
  Pin to a specific upstream commit for reproducibility, matching this
  project's existing pattern of pinning exact versions (Hugo 0.132.0,
  `requests==2.32.3`): fetch commit `9508b4e1dd2400039b76c971880eebdd89cacc61`
  (`wiedehopf/tar1090` `master`, as of this design) via
  `git archive --remote` or a tagged tarball download, not a live `master`
  clone. `data/` and `chunks/` subdirectories are left empty (`.gitkeep`'d)
  — the pipeline populates them.
- Hand-edit the vendored `config.js`: set the page title to "Trabzon
  Overflight Tracker — Live", leave `flightawareLinks` disabled (consistent
  with this project's existing no-origin/destination-data stance — no
  third-party route/identity lookups). No map-center config needed; it's
  read from `receiver.json`.
- Vendored as a point-in-time snapshot, not a submodule or live fetch —
  future tar1090 upstream updates require manual re-vendoring. Noted in the
  README.
- `layouts/index.html` gets one new link: "Live view →" to
  `{{ "tar1090/" | relURL }}`, consistent with the existing homepage list.
- README gets a short new section describing the live view and the
  vendoring caveat.

## Testing

`write_snapshot`, `append_chunk`, and `write_receiver_json` get unit tests
following the project's existing TDD pattern: output shape assertions,
chunk-pruning behavior (writes beyond `retain` delete the oldest chunk
files and drop them from `chunks.json`), and chunk ordering
(oldest-first in the array). No test coverage for the vendored tar1090 JS
itself — out of scope, it's third-party code.

## Out of scope

- Per-calendar-date replay browsing via tar1090 (see "Why not a full
  per-date archive" above) — the existing Hugo daily archive pages remain
  the permanent record.
- Automatic re-vendoring/update mechanism for tar1090's upstream code.
- Any changes to the existing daily archive pipeline, templates, or data
  shapes.
