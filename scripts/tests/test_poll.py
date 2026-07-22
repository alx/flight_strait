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
        "https://api.adsb.lol/v2/point/40.995/39.789/150", timeout=10
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
