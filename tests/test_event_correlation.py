import json

from fastapi.testclient import TestClient
import pytest

import app.main as main_module
from app.processor import EventProcessor


client = TestClient(main_module.app)


@pytest.fixture(autouse=True)
def isolated_processor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "processor", EventProcessor())


def event(minute: int, correlation_id: str | None = None) -> dict:
    payload = {
        "source": "sensor-alpha",
        "metric": "temperature",
        "value": 72.4,
        "timestamp": f"2026-09-28T17:{minute:02d}:00Z",
    }
    if correlation_id is not None:
        payload["correlation_id"] = correlation_id
    return payload


def test_correlation_id_is_normalized_and_part_of_event_identity() -> None:
    first = client.post("/events", json=event(0, " incident-42 "))
    duplicate = client.post("/events", json=event(0, "incident-42"))
    other_correlation = client.post("/events", json=event(0, "incident-43"))

    assert first.status_code == 200
    assert first.json()["correlation_id"] == "incident-42"
    assert duplicate.json()["duplicate"] is True
    assert duplicate.json()["event_id"] == first.json()["event_id"]
    assert other_correlation.json()["accepted"] is True
    assert other_correlation.json()["event_id"] != first.json()["event_id"]


def test_correlation_filter_spans_history_pagination_and_export() -> None:
    expected = [
        client.post("/events", json=event(0, "incident-42")).json(),
        client.post("/events", json=event(1, "incident-42")).json(),
    ]
    client.post("/events", json=event(2, "incident-99"))

    recent = client.get("/events/recent", params={"correlation_id": " incident-42 "})
    page = client.get("/events/page", params={"correlation_id": "incident-42"})
    exported = client.get("/events/export", params={"correlation_id": "incident-42"})

    assert recent.status_code == 200
    assert recent.json() == list(reversed(expected))
    assert page.json()["events"] == list(reversed(expected))
    assert [json.loads(line) for line in exported.text.splitlines()] == list(reversed(expected))
    assert exported.headers["x-event-count"] == "2"


def test_correlation_id_survives_export_and_replay_and_rejects_invalid_values() -> None:
    created = client.post("/events", json=event(0, "incident-42"))
    exported = client.get("/events/export", params={"correlation_id": "incident-42"})
    main_module.processor = EventProcessor()
    replayed = client.post(
        "/events/replay",
        content=exported.content,
        headers={"Content-Type": "application/x-ndjson"},
    )

    assert replayed.status_code == 200
    assert replayed.json()["results"][0]["correlation_id"] == "incident-42"
    assert replayed.json()["results"][0]["event_id"] == created.json()["event_id"]
    assert client.post("/events", json=event(1, "   ")).status_code == 422
    assert client.post("/events", json=event(1, "x" * 101)).status_code == 422
    assert client.get("/events/recent", params={"correlation_id": "   "}).status_code == 422


def test_correlation_summary_spans_streams_and_classifies_health() -> None:
    events = [
        event(0, " incident-42 "),
        {
            **event(1, "incident-42"),
            "source": "sensor-beta",
            "metric": "pressure",
            "value": 300.0,
        },
        event(3, "incident-42"),
        event(2, "incident-42"),
        {**event(4, "incident-42"), "source": "sensor-beta"},
    ]
    for payload in events:
        assert client.post("/events", json=payload).status_code == 200
    client.post("/events", json=event(3, "incident-other"))

    response = client.get("/events/correlations/incident-42")

    assert response.status_code == 200
    assert response.json() == {
        "correlation_id": "incident-42",
        "health": "watch",
        "event_count": 5,
        "anomaly_count": 1,
        "anomaly_rate": 0.2,
        "out_of_order_count": 1,
        "out_of_order_rate": 0.2,
        "sources": ["sensor-alpha", "sensor-beta"],
        "metrics": ["pressure", "temperature"],
        "first_timestamp": "2026-09-28T17:00:00+00:00",
        "last_timestamp": "2026-09-28T17:04:00+00:00",
        "duration_seconds": 240.0,
    }


def test_correlation_summary_reports_critical_health() -> None:
    payload = event(0, "incident-critical")
    payload["value"] = 200.0
    client.post("/events", json=payload)

    response = client.get("/events/correlations/incident-critical")

    assert response.status_code == 200
    assert response.json()["health"] == "critical"
    assert response.json()["duration_seconds"] == 0.0


def test_correlation_summary_validates_and_requires_retained_events() -> None:
    missing = client.get("/events/correlations/missing")
    blank = client.get("/events/correlations/%20%20%20")
    too_long = client.get(f"/events/correlations/{'x' * 101}")

    assert missing.status_code == 404
    assert missing.json()["detail"] == "correlation not found in retained history"
    assert blank.status_code == 422
    assert blank.json()["detail"] == "correlation_id must not be blank"
    assert too_long.status_code == 422
