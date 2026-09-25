from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.main as main
from app.models import TelemetryEvent
from app.processor import EventProcessor


def payload(**overrides) -> dict:
    event = {
        "source": "sensor-a",
        "metric": "temperature",
        "value": 72.4,
        "timestamp": "2026-09-25T12:00:00Z",
    }
    event.update(overrides)
    return event


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_model_rejects_non_finite_values(value: float) -> None:
    with pytest.raises(ValidationError, match="finite number"):
        TelemetryEvent(
            source="sensor-a",
            metric="temperature",
            value=value,
            timestamp=datetime.now(timezone.utc),
        )


@pytest.mark.parametrize("field", ["source", "metric"])
def test_model_rejects_blank_identifiers(field: str) -> None:
    with pytest.raises(ValidationError, match="at least 1 character"):
        TelemetryEvent.model_validate(payload(**{field: "   \t"}))


def test_identifiers_are_trimmed_before_processing_and_deduplication() -> None:
    processor = EventProcessor()
    timestamp = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)
    first = TelemetryEvent(source=" sensor-a ", metric=" temperature ", value=72.4,
                           timestamp=timestamp)
    replay = TelemetryEvent(source="sensor-a", metric="temperature", value=72.4,
                            timestamp=timestamp)

    accepted = processor.process(first)
    duplicate = processor.process(replay)

    assert accepted["source"] == "sensor-a"
    assert accepted["metric"] == "temperature"
    assert duplicate["duplicate"] is True


def test_api_rejects_non_finite_json_without_mutating_stats() -> None:
    main.processor = EventProcessor()
    client = TestClient(main.app)
    response = client.post(
        "/events",
        content=(
            '{"source":"sensor-a","metric":"temperature","value":NaN,'
            '"timestamp":"2026-09-25T12:00:00Z"}'
        ),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert main.processor.stats()["processed"] == 0


def test_batch_rejects_blank_identifier_atomically() -> None:
    main.processor = EventProcessor()
    client = TestClient(main.app)
    response = client.post(
        "/events/batch",
        json=[payload(), payload(source="   ", timestamp="2026-09-25T12:00:01Z")],
    )

    assert response.status_code == 422
    assert main.processor.stats()["processed"] == 0
