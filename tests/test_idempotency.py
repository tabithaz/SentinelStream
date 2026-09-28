from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import pytest

from app import main as main_module
from app.idempotency import analyze_idempotency_window
from app.models import TelemetryEvent
from app.processor import EventProcessor, IdempotencyConflictError


client = TestClient(main_module.app)


def test_replays_inside_window_are_suppressed() -> None:
    report = analyze_idempotency_window([2, 5, 10], 30)
    assert report.suppressed_replays == 3
    assert report.expired_replays == 0
    assert report.status == "healthy"


def test_expired_replays_are_reported() -> None:
    ages = [5] * 19 + [60]
    report = analyze_idempotency_window(ages, 30)
    assert report.expired_replays == 1
    assert report.suppression_rate_percent == 95.0
    assert report.status == "degraded"


def test_many_expired_replays_are_critical() -> None:
    report = analyze_idempotency_window([5, 40, 50, 60], 30)
    assert report.status == "critical"


def test_no_replays_is_healthy() -> None:
    report = analyze_idempotency_window([], 30)
    assert report.replayed_events == 0
    assert report.status == "healthy"


def test_invalid_settings_are_rejected() -> None:
    with pytest.raises(ValueError):
        analyze_idempotency_window([1], 0)
    with pytest.raises(ValueError):
        analyze_idempotency_window([-1], 30)


def payload(value: float = 72.0, second: int = 0) -> dict:
    return {
        "source": "sensor-alpha",
        "metric": "temperature",
        "value": value,
        "timestamp": f"2026-09-28T15:00:{second:02d}Z",
    }


@pytest.fixture(autouse=True)
def isolated_processor(monkeypatch: pytest.MonkeyPatch) -> EventProcessor:
    processor = EventProcessor()
    monkeypatch.setattr(main_module, "processor", processor)
    return processor


def test_single_event_retry_returns_original_result_without_state_mutation(
    isolated_processor: EventProcessor,
) -> None:
    first = client.post(
        "/events", json=payload(), headers={"Idempotency-Key": "producer-42"}
    )
    replay = client.post(
        "/events", json=payload(), headers={"Idempotency-Key": "producer-42"}
    )

    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert first.headers["idempotency-replayed"] == "false"
    assert replay.headers["idempotency-replayed"] == "true"
    assert isolated_processor.stats()["processed"] == 1
    assert isolated_processor.stats()["duplicates"] == 0


def test_key_reuse_for_different_payload_is_rejected(
    isolated_processor: EventProcessor,
) -> None:
    client.post("/events", json=payload(), headers={"Idempotency-Key": "producer-42"})
    conflict = client.post(
        "/events", json=payload(value=73.0), headers={"Idempotency-Key": "producer-42"}
    )
    malformed = client.post(
        "/events", json=payload(), headers={"Idempotency-Key": "contains spaces"}
    )

    assert conflict.status_code == 409
    assert "different event payload" in conflict.json()["detail"]
    assert malformed.status_code == 422
    assert isolated_processor.stats()["processed"] == 1


def test_batch_retry_is_idempotent(isolated_processor: EventProcessor) -> None:
    events = [payload(second=0), payload(value=150.0, second=1)]
    first = client.post(
        "/events/batch", json=events, headers={"Idempotency-Key": "batch-42"}
    )
    replay = client.post(
        "/events/batch", json=events, headers={"Idempotency-Key": "batch-42"}
    )

    assert first.json() == replay.json()
    assert replay.headers["idempotency-replayed"] == "true"
    assert isolated_processor.stats()["processed"] == 2
    assert isolated_processor.stats()["duplicates"] == 0


def test_idempotency_window_is_bounded_and_evicts_least_recent_key() -> None:
    processor = EventProcessor(idempotency_size=2)
    first = TelemetryEvent(**payload(second=0))
    second = TelemetryEvent(**payload(value=73.0, second=1))
    third = TelemetryEvent(**payload(value=74.0, second=2))

    processor.process_idempotent(first, "first")
    processor.process_idempotent(second, "second")
    processor.process_idempotent(third, "third")
    result, replayed = processor.process_idempotent(first, "first")

    assert result["duplicate"] is True
    assert replayed is False
    assert processor.stats()["cardinality"]["idempotency_keys"] == 2
    assert processor.stats()["cardinality"]["idempotency_limit"] == 2


def test_concurrent_same_key_processes_exactly_once() -> None:
    processor = EventProcessor()
    event = TelemetryEvent(**payload())

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(
            executor.map(
                lambda _: processor.process_idempotent(event, "concurrent-key"),
                range(50),
            )
        )

    assert sum(not replayed for _, replayed in results) == 1
    assert all(result["accepted"] is True for result, _ in results)
    assert processor.stats()["processed"] == 1
    assert processor.stats()["duplicates"] == 0


def test_invalid_idempotency_size_is_rejected() -> None:
    with pytest.raises(ValueError, match="idempotency_size"):
        EventProcessor(idempotency_size=0)


def test_processor_rejects_conflicting_direct_key_use() -> None:
    processor = EventProcessor()
    processor.process_idempotent(TelemetryEvent(**payload()), "key")

    with pytest.raises(IdempotencyConflictError, match="different event payload"):
        processor.process_idempotent(TelemetryEvent(**payload(value=99.0)), "key")
