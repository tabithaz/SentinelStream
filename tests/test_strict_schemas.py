from datetime import datetime, timezone
import json

from fastapi.testclient import TestClient
import pytest

from app import main
from app.processor import EventProcessor


client = TestClient(main.app)


def event(**overrides: object) -> dict:
    payload = {
        "source": "sensor-alpha",
        "metric": "temperature",
        "value": 72.4,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    payload.update(overrides)
    return payload


@pytest.fixture(autouse=True)
def isolated_processor(monkeypatch: pytest.MonkeyPatch) -> EventProcessor:
    processor = EventProcessor()
    monkeypatch.setattr(main, "processor", processor)
    monkeypatch.setenv("SENTINELSTREAM_INGEST_RATE_LIMIT", "0")
    monkeypatch.setenv("SENTINELSTREAM_MAX_CONCURRENT_INGESTION", "0")
    return processor


def test_single_event_rejects_unknown_fields_before_mutation(
    isolated_processor: EventProcessor,
) -> None:
    response = client.post("/events", json=event(sequence_number=42))

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "extra_forbidden"
    assert response.json()["detail"][0]["loc"] == ["body", "sequence_number"]
    assert isolated_processor.stats()["processed"] == 0


def test_batch_rejects_unknown_fields_atomically(
    isolated_processor: EventProcessor,
) -> None:
    response = client.post(
        "/events/batch",
        json=[event(source="sensor-good"), event(source="sensor-bad", valu=72.4)],
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", 1, "valu"]
    assert isolated_processor.stats()["processed"] == 0


def test_replay_reports_line_with_unknown_field_without_mutation(
    isolated_processor: EventProcessor,
) -> None:
    body = "\n".join(
        (
            json.dumps(event(source="sensor-good")),
            json.dumps(event(source="sensor-bad", sequence_number=42)),
        )
    )

    response = client.post(
        "/events/replay",
        content=body,
        headers={"Content-Type": "application/x-ndjson"},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "replay line 2: invalid telemetry event"}
    assert isolated_processor.stats()["processed"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {
            "thresholds": {"temperature": {"minimum": 0, "maximum": 80}},
            "change_reason": "unexpected body field",
        },
        {
            "thresholds": {
                "temperature": {"minimum": 0, "maximum": 80, "units": "C"}
            }
        },
    ],
)
def test_threshold_updates_reject_unknown_fields_atomically(
    payload: dict,
    isolated_processor: EventProcessor,
) -> None:
    response = client.put(
        "/events/thresholds",
        headers={"If-Match": '"1"'},
        json=payload,
    )

    assert response.status_code == 422
    assert any(item["type"] == "extra_forbidden" for item in response.json()["detail"])
    assert isolated_processor.threshold_configuration()["version"] == 1
