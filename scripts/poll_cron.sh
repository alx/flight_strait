#!/usr/bin/env bash
# Runs one poll/aggregate cycle and pushes the result. Intended to be invoked
# every 5 minutes by cron or a systemd timer (see README.md "Running the
# poller yourself" for setup). Safe to run concurrently with itself thanks to
# the flock below, and safe to run alongside GitHub Actions workflow_dispatch
# runs since it always rebases before pushing.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

exec 200>"$REPO_DIR/.poll_cron.lock"
flock -n 200 || { echo "Another poll_cron.sh run is still in progress, skipping."; exit 0; }

if [ -x "$REPO_DIR/.venv/bin/python" ]; then
  PYTHON="$REPO_DIR/.venv/bin/python"
else
  PYTHON="python3"
fi

git pull --rebase --quiet origin main

PYTHONPATH="$REPO_DIR" "$PYTHON" -m scripts.run

git add data/raw data/daily content/days static/tar1090/data static/tar1090/chunks

if git diff --cached --quiet; then
  echo "No changes to commit."
  exit 0
fi

git commit -m "Update flight data $(date -u +%Y-%m-%dT%H:%M:%SZ)" --quiet
git push --quiet origin main
