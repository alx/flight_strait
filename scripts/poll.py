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
