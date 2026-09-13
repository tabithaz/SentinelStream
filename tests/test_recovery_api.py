from fastapi.testclient import TestClient

import app.main as main
from app.processor import EventProcessor


def test_recovery_summary_uses_recent_failure_streak() -> None:
    main.processor = EventProcessor()
    client = TestClient(main.app)

    events = [
        {
            "source": "alpha",
            "metric": "temperature",
            "value": 20.0,
            "timestamp": f"2026-09-13T10:00:{second:02d}Z",
        }
        for second in range(7)
    ]
    events.extend(
        {
            "source": "alpha",
            "metric": "temperature",
            "value": 150.0,
            "timestamp": f"2026-09-13T10:00:{second:02d}Z",
        }
        for second in range(7, 10)
    )
    assert client.post("/events/batch", json=events).status_code == 200

    response = client.get("/events/recovery")
    assert response.status_code == 200
    payload = response.json()

    assert payload["action"] == "throttle"
    assert payload["consecutive_failures"] == 3
    assert payload["error_rate"] == 0.3
    assert payload["retry_delay_seconds"] == 10.0
    assert payload["shed_load_percent"] == 25.0


def test_recovery_summary_opens_circuit_for_queue_pressure() -> None:
    main.processor = EventProcessor()
    client = TestClient(main.app)

    events = [
        {
            "source": "alpha",
            "metric": "signal",
            "value": float(index),
            "timestamp": f"2026-09-13T11:00:{index:02d}Z",
        }
        for index in range(6)
    ]
    assert client.post("/events/batch", json=events).status_code == 200

    response = client.get(
        "/events/recovery?window_seconds=60&windows=1"
        "&service_capacity_per_window=1&queue_capacity=5"
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["action"] == "open_circuit"
    assert payload["queue_utilization"] == 1.0
    assert payload["backpressure_status"] == "critical"
    assert payload["consecutive_failures"] == 0


def test_recovery_summary_can_isolate_a_source() -> None:
    main.processor = EventProcessor()
    client = TestClient(main.app)

    events = [
        {
            "source": "alpha",
            "metric": "temperature",
            "value": 20.0,
            "timestamp": "2026-09-13T12:00:00Z",
        },
        {
            "source": "beta",
            "metric": "temperature",
            "value": 150.0,
            "timestamp": "2026-09-13T12:00:01Z",
        },
        {
            "source": "beta",
            "metric": "temperature",
            "value": 151.0,
            "timestamp": "2026-09-13T12:00:02Z",
        },
    ]
    assert client.post("/events/batch", json=events).status_code == 200

    response = client.get("/events/recovery?source=alpha")
    assert response.status_code == 200
    payload = response.json()

    assert payload["source"] == "alpha"
    assert payload["action"] == "normal"
    assert payload["error_rate"] == 0.0
    assert payload["consecutive_failures"] == 0
