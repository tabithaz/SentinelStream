from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest

import app.main as main_module
from app.models import TelemetryEvent
from app.processor import EventProcessor


client = TestClient(main_module.app)


@pytest.fixture(autouse=True)
def isolated_processor(monkeypatch: pytest.MonkeyPatch) -> EventProcessor:
    processor = EventProcessor()
    monkeypatch.setattr(main_module, "processor", processor)
    return processor


def event(minute: int = 0) -> TelemetryEvent:
    return TelemetryEvent(
        source="sensor-alpha",
        metric="temperature",
        value=72.4 + minute,
        timestamp=datetime(2026, 9, 27, 12, minute, tzinfo=timezone.utc),
    )


def test_event_can_be_retrieved_by_deterministic_id() -> None:
    created = client.post("/events", json=event().model_dump(mode="json"))

    response = client.get(f"/events/id/{created.json()['event_id']}")

    assert created.status_code == 200
    assert response.status_code == 200
    assert response.json() == created.json()


def test_event_lookup_distinguishes_invalid_missing_and_duplicate_ids() -> None:
    created = client.post("/events", json=event().model_dump(mode="json"))
    duplicate = client.post("/events", json=event().model_dump(mode="json"))
    invalid = client.get("/events/id/not-a-sha256-id")
    missing = client.get(f"/events/id/{'0' * 64}")

    assert duplicate.json()["event_id"] == created.json()["event_id"]
    assert client.get(f"/events/id/{duplicate.json()['event_id']}").status_code == 200
    assert invalid.status_code == 422
    assert missing.status_code == 404
    assert missing.json()["detail"] == "event not found in retained history"


def test_event_lookup_respects_bounded_history() -> None:
    processor = EventProcessor(history_size=2)
    first = processor.process(event())
    processor.process(event(1))
    latest = processor.process(event(2))

    assert processor.event_by_id(first["event_id"]) is None
    assert processor.event_by_id(latest["event_id"]) == latest
