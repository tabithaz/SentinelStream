from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app, processor

client = TestClient(app)


def _event(source: str, metric: str, value: float, second: int) -> dict:
    return {
        "source": source,
        "metric": metric,
        "value": value,
        "timestamp": datetime(2026, 9, 10, 12, 0, second, tzinfo=timezone.utc).isoformat(),
    }


def test_quality_summary_reports_healthy_stream() -> None:
    processor.__init__()
    client.post("/events", json=_event("sensor-a", "temperature", 70.0, 1))
    client.post("/events", json=_event("sensor-b", "pressure", 120.0, 2))

    response = client.get("/events/quality-summary")

    assert response.status_code == 200
    assert response.json() == {
        "received": 2,
        "accepted": 2,
        "duplicates": 0,
        "anomalies": 0,
        "acceptance_rate": 1.0,
        "duplicate_rate": 0.0,
        "anomaly_rate": 0.0,
        "quality": "healthy",
    }


def test_quality_summary_flags_duplicate_pressure() -> None:
    processor.__init__()
    event = _event("sensor-a", "temperature", 70.0, 3)
    client.post("/events", json=event)
    client.post("/events", json=event)
    client.post("/events", json=event)
    client.post("/events", json=_event("sensor-b", "temperature", 71.0, 4))

    body = client.get("/events/quality-summary").json()

    assert body["received"] == 4
    assert body["accepted"] == 2
    assert body["duplicates"] == 2
    assert body["duplicate_rate"] == 0.5
    assert body["quality"] == "unreliable"


def test_quality_summary_flags_anomaly_pressure() -> None:
    processor.__init__()
    client.post("/events", json=_event("sensor-a", "temperature", 130.0, 5))
    client.post("/events", json=_event("sensor-b", "temperature", 70.0, 6))
    client.post("/events", json=_event("sensor-c", "temperature", 71.0, 7))
    client.post("/events", json=_event("sensor-d", "temperature", 72.0, 8))
    client.post("/events", json=_event("sensor-e", "temperature", 73.0, 9))

    body = client.get("/events/quality-summary").json()

    assert body["anomaly_rate"] == 0.2
    assert body["quality"] == "degraded"
