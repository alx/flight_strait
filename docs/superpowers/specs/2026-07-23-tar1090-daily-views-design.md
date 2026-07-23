# tar1090 Per-Day Trace Views — Design

## Overview

Extend the existing tar1090 live view (`/tar1090/`, a rolling 24-hour map,
see `docs/superpowers/specs/2026-07-22-tar1090-live-view-design.md`) with a
**permanent, per-calendar-day trace view** at `/tar1090/days/<date>/` for
every day in the archive. Each page shows that single day's full aircraft
trails, rendered with the same tar1090 map UI used for the live view.

This sits alongside two existing, unchanged pages for the same data:

- `/tar1090/` — rolling last-24h live view (unchanged).
- `/days/<date>/` — permanent per-day archive: flight table + Leaflet map
  (unchanged).

`/tar1090/days/<date>/` is a third, complementary view: the tar1090 map UI's
richer rendering (trails, altitude coloring, aircraft icons, sidebar detail),
scoped to one calendar day instead of a trailing window.

## Why this is feasible

tar1090's "chunk history" mechanism (`chunks/chunks.json` +
`chunks/chunk_<ts>.json`), already used to render trails on the rolling live
view, is just a sequence of snapshot files loaded once at page load to draw
trails — it has no notion of "live" vs. "historical" data. Generating a full
day's chunk sequence and pointing a tar1090 instance at it produces a
day-scoped trace view for free, with no changes to tar1090's application
logic.

Confirmed from the vendored source:

- `chunks/chunks.json` and `data/aircraft.json` are fetched with paths
  **relative to the page URL** (`early.js`), not relative to the script
  files' own location. So a tar1090 page can live at any directory depth and
  still correctly load a data/chunks folder placed next to it.
- `index.html`'s asset references (`script.js`, `style.css`, `libs/*`,
  `images/*`, `config.js`, etc.) are also plain relative paths, one level
  each — adjustable to the page's actual depth without touching the
  vendored files themselves.

This means the daily views can be built as **thin, per-day HTML shells that
reference the one shared, unmodified vendored asset tree**, with only small
generated JSON data alongside each shell — no duplication of the ~5.5MB,
337-file tar1090 app per day, and no hand-editing of vendored JS beyond what
already exists (`config.js`).

## Output layout

```
public/
  tar1090/
    script.js, style.css, libs/, images/, config.js, ...   ← shared, vendored, untouched
    index.html                                               ← existing rolling 24h live view
    data/, chunks/                                           ← existing live feed (unchanged)
    days/
      index.html            ← new: reverse-chronological list of days
      2026-07-22/
        index.html           ← new: thin shell, Hugo-rendered
        data/aircraft.json, receiver.json
        chunks/chunk_*.json, chunks.json
      2026-07-23/
        index.html
        data/
        chunks/
```

## Data pipeline extension

Reuses the existing `write_snapshot`, `append_chunk`, `write_receiver_json`
functions from `scripts/tar1090_feed.py` (built for the rolling view) —
called a second time per poll in `scripts/run.py`, targeting
`static/tar1090/days/<date>/` (today's date), alongside the existing calls
that target `static/tar1090/data` / `static/tar1090/chunks`.

- **No pruning within a day.** `append_chunk`'s `retain` parameter is passed
  a generous fixed ceiling (e.g. 400) instead of the rolling view's 289 — a
  day naturally produces at most ~288 five-minute-cadence chunks, so this
  ceiling is a safety bound against runaway growth (e.g. a misconfigured
  cron), not a real limit.
- **Day rollover.** No extra state tracking needed: on every poll, after
  writing today's snapshot/chunk, the pipeline finalizes every *other*
  existing `static/tar1090/days/<date>/` directory (i.e. every date
  directory except today's) by overwriting its `data/aircraft.json` to an
  **empty aircraft list** (`write_snapshot([], ...)`). This is idempotent —
  re-emptying an already-empty file on every subsequent poll is a harmless
  no-op — so it needs no memory of "which date was previous" and
  self-heals after missed runs or manual reruns. A finished day's page
  therefore never shows a "ghost" aircraft frozen at its last observed
  position, only the completed trail from that day's chunk history.
  `receiver.json` and the chunk files are untouched by finalization.
- **Backfill.** A new one-time, manually-run script (not part of the
  recurring GitHub Actions pipeline) reconstructs
  `static/tar1090/days/<date>/` for each already-archived day by replaying
  its `data/raw/<date>.jsonl` through the same `write_snapshot` /
  `append_chunk` / `write_receiver_json` functions, then finalizing
  (emptying `aircraft.json`) since all backfilled days are already over.
  This covers the two days that predate this feature (2026-07-22,
  2026-07-23).
- **Workflow.** `.github/workflows/track.yml`'s "Commit updated data" step's
  `git add` gets `static/tar1090/days` added alongside the existing paths.

## UI integration

- **Thin per-day shell:** a new Hugo content section (e.g. `tar1090days`,
  one `.md` file per date, mirroring the existing `days` section) with a
  custom permalink so it renders to `/tar1090/days/<date>/index.html`. Its
  layout is a minimal HTML page referencing the shared tar1090 assets via
  `relURL` (so paths resolve correctly under the site's `/flight_strait/`
  GitHub Pages subpath) — the vendored `index.html`'s `<head>`/`<script>`
  block, retargeted one directory level deeper.
- **Day index:** `/tar1090/days/` — a Hugo-rendered list page, reverse
  chronological, one link per day, mirroring the homepage's day list
  structure.
- **Cross-links:** `layouts/days/single.html` (the existing per-day archive
  page) gets one new link: "View live trace map →" to
  `{{ printf "tar1090/days/%s/" $date | relURL }}`.
- **No changes** to `static/tar1090/config.js`, `early.js`, `script.js`, or
  any other vendored file — the per-day views are pure data + a new thin
  shell built by this project, not a modification of tar1090 itself.

## Out of scope

- Any change to the existing rolling 24h live view (`/tar1090/`) or the
  existing per-day Leaflet archive (`/days/<date>/`) — both continue to work
  exactly as they do today.
- Automatic pruning/expiry of daily views — per the "all days, forever"
  decision, `static/tar1090/days/<date>/` accumulates permanently, matching
  how `data/daily/<date>.json` and `content/days/<date>.md` already
  accumulate permanently.
- Any modification to vendored tar1090 source files beyond the existing,
  already-established `config.js` hand-edits.

## Testing

- `scripts/tar1090_feed.py`'s existing functions are reused as-is — no new
  unit tests needed for the write/append/prune logic itself, since it's the
  same code already covered by `scripts/tests/test_tar1090_feed.py`.
- New unit tests for: `scripts/run.py`'s day-rollover finalization logic
  (previous day's `aircraft.json` becomes empty on date change), and the
  backfill script (given a fixture `data/raw/<date>.jsonl`, produces the
  expected `static/tar1090/days/<date>/` chunk sequence).
- No test coverage for the vendored tar1090 JS or the thin Hugo shell's
  rendered output beyond a build-time check (`hugo --minify` succeeds,
  `public/tar1090/days/<date>/index.html` and its `data`/`chunks`
  subdirectories exist) — consistent with the existing live-view feature's
  testing approach.
