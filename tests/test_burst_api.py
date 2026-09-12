from fastapi.testclient import TestClient

import app.main as main
from app.processor import EventProcessor


def test_burst_summary_uses_live_event_windows() -> None:
    main.processor = EventProcessor()
    client = TestClient(main.app)

    events = [
        {"source": "alpha", "metric": "signal", "value": 1.0, "timestamp": "2026-09-12T10:02:50Z"},
        {"source": "alpha", "metric": "signal", "value": 2.0, "timestamp": "2026-09-12T10:03:10Z"},
        {"source": "alpha", "metric": "signal", "value": 3.0, "timestamp": "2026-09-12T10:03:20Z"},
        {"source": "alpha", "metric": "signal", "value": 4.0, "timestamp": "2026-09-12T10:03:30Z"},
        {"source": "alpha", "metric": "signal", "value": 5.0, "timestamp": "2026-09-12T10:03:40Z"},
        {"source": "alpha", "metric": "signal", "value": 6.0, "timestamp": "2026-09-12T10:03:50Z"},
    ]
    assert client.post("/events/batch", json=events).status_code == 200

    response = client.get("/events/bursts?window_seconds=60&windows=4&multiplier=2")
    assert response.status_code == 200
    payload = response.json()

    assert payload["window_counts"] == [0, 0, 1, 5]
    assert payload["windows"] == 4
    assert payload["average_events"] == 1.5
    assert payload["peak_events"] == 5
    assert payload["burst_windows"] == 1
    assert payload["burst_rate_percent"] == 25.0
    assert payload["status"] == "bursty"
    assert payload["anchor_timestamp"] == "2026-09-12T10:03:50+00:00"


def test_burst_summary_can_isolate_a_source() -> None:
    main.processor = EventProcessor()
    client = TestClient(main.app)

    events = [
        {"source": "alpha", "metric": "signal", "value": 1.0, "timestamp": "2026-09-12T10:00:00Z"},
        {"source": "alpha", "metric": "signal", "value": 2.0, "timestamp": "2026-09-12T10:00:10Z"},
        {"source": "beta", "metric": "signal", "value": 1.0, "timestamp": "2026-09-12T10:00:20Z"},
        {"source": "beta", "metric": "signal", "value": 2.0, "timestamp": "2026-09-12T10:00:30Z"},
        {"source": "beta", "metric": "signal", "value": 3.0, "timestamp": "2026-09-12T10:00:40Z"},
    ]
    assert client.post("/events/batch", json=events).status_code == 200

    response = client.get("/events/bursts?window_seconds=60&windows=2&source=alpha")
    assert response.status_code == 200
    payload = response.json()

    assert payload["source"] == "alpha"
    assert payload["window_counts"] == [0, 2]
    assert payload["peak_events"] == 2
    assert payload["status"] == "stable"


def test_burst_summary_rejects_invalid_multiplier() -> None:
    main.processor = EventProcessor()
    client = TestClient(main.app)

    response = client.get("/events/bursts?multiplier=1")
    assert response.status_code == 422
