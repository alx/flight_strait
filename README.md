# Trabzon Overflight Tracker

A Hugo static site that publishes one page per day of long-haul flights
observed passing near Trabzon, Turkey — a node on the Black Sea / Caucasus
overflight corridor used by Europe–Gulf and Europe–Asia traffic. Data comes
from the free [`api.adsb.lol`](https://api.adsb.lol) ADS-B aggregation API.

Live site: https://alx.github.io/flight_strait/

## How it works

Polling happens outside GitHub Actions, on a machine running
`scripts/poll_cron.sh` every 5 minutes (see [Running the poller
yourself](#running-the-poller-yourself) below). Each run:

1. **Poll**: `scripts/poll.py` queries `api.adsb.lol` for aircraft within
   150nm of Trabzon (40.995°N, 39.789°E) and appends the raw response as one
   JSON line to `data/raw/<UTC-date>.jsonl` (permanent, append-only).
2. **Aggregate**: `scripts/aggregate.py` reads the day's raw sightings,
   groups them into one track per aircraft (by ICAO hex + callsign), and
   computes first/last-seen times, min/max altitude, and closest-approach
   distance to Trabzon. Writes `data/daily/<UTC-date>.json` (overwritten on
   every poll) and `content/days/<UTC-date>.md`.
3. **Live feed**: `scripts/tar1090_feed.py` writes a current-position
   snapshot and a rolling 24-hour window of history chunks in
   [readsb](https://github.com/wiedehopf/readsb)'s own JSON format, consumed
   directly by the vendored [tar1090](https://github.com/wiedehopf/tar1090)
   web interface at `/tar1090/` — no server process required, tar1090 is
   pure client-side JS fetching relative JSON files.
4. **Commit & push**: the poller commits the updated data/content files and
   pushes to `main`.

That push triggers a GitHub Actions workflow (`.github/workflows/track.yml`)
which builds the site with `hugo --minify` and deploys it to GitHub Pages.
(An earlier version of this workflow polled on a `schedule:` trigger, but
GitHub Actions throttles scheduled runs heavily on public repos — the
configured `*/5 * * * *` cron was actually firing every 1-3 hours — so
polling moved to a self-hosted cron job instead.)

The day-boundary and all timestamps use UTC throughout.

## Site structure

- `/` — archive of all days, reverse chronological, plus a link to the live
  view.
- `/tar1090/` — live, rolling 24-hour map view (vendored tar1090, pinned to
  commit `9508b4e1dd2400039b76c971880eebdd89cacc61`; re-vendor manually to
  pick up upstream updates — there's no automatic update mechanism).
- `/days/<date>/` — per-day table (callsign, hex, registration, type,
  first/last seen, altitude, closest approach to Trabzon) plus a Leaflet map
  showing the query radius, the Trabzon reference point, and each flight's
  track. This is the permanent archive; tar1090's live view only shows a
  rolling 24-hour window, not indexed by calendar date.

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

## Running the poller yourself

The poller is a plain script (`scripts/poll_cron.sh`) driven by an ordinary
cron job or systemd timer — no GitHub Actions involved. It pulls the latest
commit, runs one poll/aggregate cycle, and pushes the result. It's safe to
run this on more than one machine (or alongside manual GitHub Actions
`workflow_dispatch` runs) since it always rebases before pushing.

### 1. Clone and set up a virtualenv

```bash
git clone git@github.com:alx/flight_strait.git
cd flight_strait
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
```

`scripts/poll_cron.sh` automatically uses `.venv/bin/python` if that
directory exists, so no activation step is needed for cron.

### 2. Set up push access

The machine needs an SSH key (or credential helper) that can push to this
repo without a password prompt, since cron has no terminal to type one
into:

```bash
ssh-keygen -t ed25519 -C "flight-strait-poller@$(hostname)" -f ~/.ssh/flight_strait_deploy
# add ~/.ssh/flight_strait_deploy.pub as a Deploy Key (with write access)
# under the repo's Settings -> Deploy keys, then:
git config core.sshCommand "ssh -i ~/.ssh/flight_strait_deploy -o IdentitiesOnly=yes"
```

Also make sure `git config user.name` / `user.email` are set (globally or
in this repo) so commits have an author.

### 3. Verify it works

```bash
./scripts/poll_cron.sh
git log -1   # should show a new "Update flight data ..." commit, if the poll produced new data
```

### 4. Schedule it every 5 minutes

**systemd (recommended on Linux):**

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/flight-strait-poll.service <<EOF
[Unit]
Description=Poll flight_strait data

[Service]
Type=oneshot
ExecStart=$(pwd)/scripts/poll_cron.sh
EOF

cat > ~/.config/systemd/user/flight-strait-poll.timer <<EOF
[Unit]
Description=Run flight_strait poller every 5 minutes

[Timer]
OnCalendar=*:0/5
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl --user enable --now flight-strait-poll.timer
systemctl --user list-timers flight-strait-poll.timer   # confirm it's scheduled
loginctl enable-linger "$USER"   # keep the timer running after logout
```

**cron (alternative, any Unix):**

```bash
crontab -e
# add this line (adjust the path):
*/5 * * * * /path/to/flight_strait/scripts/poll_cron.sh >> /path/to/flight_strait/poll_cron.log 2>&1
```

Only one machine's poller (or scheduler) needs to be running for the site
to update — running it on two machines is redundant but harmless.

## Repo layout

```
scripts/               Python data pipeline (poll, aggregate, tar1090 feed, tests)
scripts/poll_cron.sh   Self-hosted cron/systemd entry point (poll, commit, push)
data/raw/               Raw per-poll sightings, one JSONL file per UTC day
data/daily/             Aggregated per-day flight tracks (JSON)
content/days/           Generated Hugo content pages, one per day
layouts/                Hugo templates (homepage, day page)
static/js/map.js        Leaflet map rendering for the daily archive pages
static/tar1090/         Vendored tar1090 live-view web interface
static/tar1090/data/    Generated current-snapshot feed (aircraft.json, receiver.json)
static/tar1090/chunks/  Generated rolling 24h history chunks
.github/workflows/      The build → deploy workflow (triggered by the poller's push)
```
