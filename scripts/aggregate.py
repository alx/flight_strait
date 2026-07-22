from pathlib import Path

from scripts.geo import haversine_nm

TRABZON = (40.995, 39.789)


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
                    "closest_trabzon_nm": None,
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

            dist_trabzon = haversine_nm(lat, lon, *TRABZON)

            if track["closest_trabzon_nm"] is None or dist_trabzon < track["closest_trabzon_nm"]:
                track["closest_trabzon_nm"] = round(dist_trabzon, 1)

    flights = sorted(tracks.values(), key=lambda t: t["first_seen"])
    return {"date": date, "flights": flights}


def write_content_page(date: str, flight_count: int, content_dir: Path) -> None:
    content_dir.mkdir(parents=True, exist_ok=True)
    page_path = content_dir / f"{date}.md"
    page_path.write_text(
        f'---\ntitle: "{date}"\ndate: {date}T00:00:00Z\nflight_count: {flight_count}\n---\n'
    )
