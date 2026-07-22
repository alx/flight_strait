import json
from pathlib import Path

from scripts.aggregate import TRABZON


def write_snapshot(ac_list: list[dict], now_epoch_s: float, data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = {"now": now_epoch_s, "messages": 0, "aircraft": ac_list}
    (data_dir / "aircraft.json").write_text(json.dumps(payload))


def write_receiver_json(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    payload = {"lat": TRABZON[0], "lon": TRABZON[1], "version": "adsb.lol-poller"}
    (data_dir / "receiver.json").write_text(json.dumps(payload))


def append_chunk(
    ac_list: list[dict], now_epoch_s: float, chunks_dir: Path, retain: int = 289
) -> None:
    chunks_dir.mkdir(parents=True, exist_ok=True)

    now_epoch_ms = int(now_epoch_s * 1000)
    filename = f"chunk_{now_epoch_ms}.json"
    payload = {"now": now_epoch_s, "messages": 0, "aircraft": ac_list}
    (chunks_dir / filename).write_text(json.dumps(payload))

    index_path = chunks_dir / "chunks.json"
    if index_path.exists():
        chunks = json.loads(index_path.read_text())["chunks"]
    else:
        chunks = []
    chunks.append(filename)

    while len(chunks) > retain:
        stale = chunks.pop(0)
        stale_path = chunks_dir / stale
        if stale_path.exists():
            stale_path.unlink()

    index_path.write_text(json.dumps({"chunks": chunks}))
