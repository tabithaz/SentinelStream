import json
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import main
from app.models import TelemetryEvent
from app.processor import EventProcessor


def _payload(second: int) -> dict:
    return {
        "source": "vehicle-a",
        "metric": "temperature",
        "value": 72.0 + second,
        "timestamp": f"2026-09-25T14:00:{second:02d}Z",
    }


def test_recent_events_filters_an_inclusive_time_window() -> None:
    processor = EventProcessor()
    for second in (5, 10, 15, 20):
        processor.process(TelemetryEvent(**_payload(second)))

    events = processor.recent_events(
        since=datetime(2026, 9, 25, 14, 0, 10, tzinfo=timezone.utc),
        until=datetime(2026, 9, 25, 14, 0, 15, tzinfo=timezone.utc),
    )

    assert [event["timestamp"] for event in events] == [
        "2026-09-25T14:00:15+00:00",
        "2026-09-25T14:00:10+00:00",
    ]


def test_export_combines_time_and_anomaly_filters(monkeypatch) -> None:
    processor = EventProcessor()
    monkeypatch.setattr(main, "processor", processor)
    client = TestClient(main.app)
    for second in (5, 10, 15, 20):
        payload = _payload(second)
        payload["value"] = 150.0 if second in (10, 15) else 72.0
        assert client.post("/events", json=payload).status_code == 200

    response = client.get(
        "/events/export",
        params={
            "since": "2026-09-25T14:00:10Z",
            "until": "2026-09-25T14:00:15Z",
            "anomalies_only": "true",
        },
    )

    assert response.status_code == 200
    assert response.headers["x-event-count"] == "2"
    events = [json.loads(line) for line in response.text.splitlines() if line]
    assert [event["timestamp"] for event in events] == [
        "2026-09-25T14:00:15+00:00",
        "2026-09-25T14:00:10+00:00",
    ]


def test_reversed_time_window_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(main, "processor", EventProcessor())
    response = TestClient(main.app).get(
        "/events/recent",
        params={
            "since": "2026-09-25T15:00:00Z",
            "until": "2026-09-25T14:00:00Z",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "since must be earlier than or equal to until"
