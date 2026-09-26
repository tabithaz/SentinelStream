import json

from fastapi.testclient import TestClient
import pytest

import app.main as main_module
from app.processor import EventProcessor


client = TestClient(main_module.app)


@pytest.fixture(autouse=True)
def isolated_processor(monkeypatch: pytest.MonkeyPatch) -> EventProcessor:
    processor = EventProcessor()
    monkeypatch.setattr(main_module, "processor", processor)
    return processor


def event(source: str, value: float, minute: int) -> dict:
    return {
        "source": source,
        "metric": "temperature",
        "value": value,
        "timestamp": f"2026-09-26T18:{minute:02d}:00Z",
    }


def encode_ndjson(records: list[dict]) -> str:
    return "".join(json.dumps(record) + "\n" for record in records)


def test_exported_events_can_be_replayed() -> None:
    records = [event("sensor-a", 72.0, 0), event("sensor-a", 145.0, 1)]
    original = client.post("/events/batch", json=records)
    exported = client.get("/events/export")
    main_module.processor = EventProcessor()

    replayed = client.post(
        "/events/replay",
        content=exported.content,
        headers={"Content-Type": "application/x-ndjson"},
    )

    assert original.status_code == 200
    assert replayed.status_code == 200
    assert replayed.json()["received"] == 2
    assert replayed.json()["accepted"] == 2
    assert replayed.json()["anomalies"] == 1
    assert replayed.json()["out_of_order"] == 0


def test_invalid_replay_is_atomic(isolated_processor: EventProcessor) -> None:
    payload = encode_ndjson([event("sensor-a", 72.0, 0)]) + "{not-json}\n"

    response = client.post(
        "/events/replay",
        content=payload,
        headers={"Content-Type": "application/x-ndjson"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "replay line 2: invalid telemetry event"
    assert isolated_processor.stats()["processed"] == 0


def test_replay_rejects_wrong_media_type_and_oversized_batches() -> None:
    wrong_type = client.post("/events/replay", content="{}")
    oversized = client.post(
        "/events/replay",
        content=encode_ndjson([event(f"sensor-{index}", 72.0, index % 60)
                               for index in range(1001)]),
        headers={"Content-Type": "application/x-ndjson"},
    )

    assert wrong_type.status_code == 415
    assert oversized.status_code == 413
    assert oversized.json()["detail"] == "replay payload exceeds 1000 events"
