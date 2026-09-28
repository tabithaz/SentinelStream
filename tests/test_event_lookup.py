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


def event(
    minute: int = 0,
    source: str = "sensor-alpha",
    metric: str = "temperature",
) -> TelemetryEvent:
    return TelemetryEvent(
        source=source,
        metric=metric,
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


def test_event_context_returns_a_bounded_chronological_window() -> None:
    created = [
        client.post("/events", json=event(minute).model_dump(mode="json")).json()
        for minute in range(5)
    ]

    response = client.get(
        f"/events/id/{created[2]['event_id']}/context?before=2&after=1"
    )

    assert response.status_code == 200
    assert response.json() == {
        "event": created[2],
        "before": created[:2],
        "after": [created[3]],
        "same_stream": False,
        "has_more_before": False,
        "has_more_after": True,
    }


def test_event_context_can_follow_only_the_target_stream() -> None:
    same_stream_before = client.post(
        "/events", json=event(0).model_dump(mode="json")
    ).json()
    client.post(
        "/events", json=event(1, source="sensor-beta").model_dump(mode="json")
    )
    client.post(
        "/events", json=event(2, metric="pressure").model_dump(mode="json")
    )
    target = client.post(
        "/events", json=event(3).model_dump(mode="json")
    ).json()
    same_stream_after = client.post(
        "/events", json=event(4).model_dump(mode="json")
    ).json()

    response = client.get(
        f"/events/id/{target['event_id']}/context"
        "?before=1&after=1&same_stream=true"
    )

    assert response.status_code == 200
    assert response.json()["before"] == [same_stream_before]
    assert response.json()["event"] == target
    assert response.json()["after"] == [same_stream_after]
    assert response.json()["same_stream"] is True


def test_event_context_validates_bounds_and_requires_retained_target() -> None:
    created = client.post("/events", json=event().model_dump(mode="json")).json()

    assert client.get(
        f"/events/id/{created['event_id']}/context?before=-1"
    ).status_code == 422
    assert client.get(
        f"/events/id/{created['event_id']}/context?after=101"
    ).status_code == 422

    missing = client.get(f"/events/id/{'0' * 64}/context")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "event not found in retained history"
