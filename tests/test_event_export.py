import json

from fastapi.testclient import TestClient
import pytest

import app.main as main
from app.processor import EventProcessor


client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_processor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "processor", EventProcessor())


def event(source: str, value: float, minute: int) -> dict:
    return {
        "source": source,
        "metric": "temperature",
        "value": value,
        "timestamp": f"2026-09-25T12:{minute:02d}:00Z",
    }


def test_export_returns_filtered_ndjson() -> None:
    client.post("/events", json=event("sensor-alpha", 70.0, 0))
    client.post("/events", json=event("sensor-alpha", 150.0, 1))
    client.post("/events", json=event("sensor-beta", 160.0, 2))

    response = client.get(
        "/events/export",
        params={"source": "sensor-alpha", "anomalies_only": "true"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert response.headers["content-disposition"] == (
        'attachment; filename="sentinelstream-events.ndjson"'
    )
    assert response.headers["x-event-count"] == "1"
    records = [json.loads(line) for line in response.text.splitlines()]
    assert records[0]["source"] == "sensor-alpha"
    assert records[0]["value"] == 150.0
    assert records[0]["anomaly"] is True


def test_export_is_bounded_and_newest_first() -> None:
    for minute in range(3):
        client.post("/events", json=event("sensor-alpha", 70.0 + minute, minute))

    response = client.get("/events/export", params={"limit": 2})

    records = [json.loads(line) for line in response.text.splitlines()]
    assert response.headers["x-event-count"] == "2"
    assert [record["value"] for record in records] == [72.0, 71.0]


def test_export_empty_history_returns_empty_ndjson() -> None:
    response = client.get("/events/export")

    assert response.status_code == 200
    assert response.headers["x-event-count"] == "0"
    assert response.content == b""


def test_export_validates_limit() -> None:
    response = client.get("/events/export", params={"limit": 1001})

    assert response.status_code == 422
