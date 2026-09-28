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
