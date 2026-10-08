from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import pytest

from app import main
from app.bulkhead import InFlightLimiter
from app.processor import EventProcessor


client = TestClient(main.app)


def event() -> dict:
    return {
        "source": "sensor-alpha",
        "metric": "temperature",
        "value": 72.4,
        "timestamp": "2026-10-08T17:00:00Z",
    }


@pytest.fixture(autouse=True)
def configured_bulkhead(monkeypatch: pytest.MonkeyPatch) -> EventProcessor:
    processor = EventProcessor()
    monkeypatch.setattr(main, "processor", processor)
    monkeypatch.setattr(main, "ingestion_concurrency_limiter", InFlightLimiter())
    monkeypatch.setenv("SENTINELSTREAM_MAX_CONCURRENT_INGESTION", "1")
    monkeypatch.setenv("SENTINELSTREAM_INGEST_RATE_LIMIT", "0")
    return processor


def test_saturated_ingestion_fails_before_state_mutation(
    configured_bulkhead: EventProcessor,
) -> None:
    assert main.ingestion_concurrency_limiter.try_acquire(1) is True
    try:
        response = client.post("/events", json=event())
    finally:
        main.ingestion_concurrency_limiter.release()

    assert response.status_code == 503
    assert response.json() == {"detail": "event ingestion concurrency limit reached"}
    assert response.headers["retry-after"] == "1"
    assert response.headers["x-concurrency-limit"] == "1"
    assert configured_bulkhead.stats()["processed"] == 0


def test_ingestion_releases_capacity_after_completion() -> None:
    first = client.post("/events", json=event())
    second_payload = event() | {"timestamp": "2026-10-08T17:00:01Z"}
    second = client.post("/events", json=second_payload)

    assert first.status_code == second.status_code == 200
    assert first.headers["x-concurrency-limit"] == "1"
    assert main.ingestion_concurrency_limiter.in_flight == 0


def test_bulkhead_is_thread_safe_and_never_exceeds_capacity() -> None:
    limiter = InFlightLimiter()

    with ThreadPoolExecutor(max_workers=20) as executor:
        acquired = list(executor.map(lambda _: limiter.try_acquire(5), range(20)))

    assert sum(acquired) == 5
    assert limiter.in_flight == 5
    for _ in range(5):
        limiter.release()
    assert limiter.in_flight == 0


@pytest.mark.parametrize("configured", ["0", "-1", "invalid"])
def test_disabled_or_invalid_configuration_preserves_existing_behavior(
    monkeypatch: pytest.MonkeyPatch,
    configured: str,
) -> None:
    monkeypatch.setenv("SENTINELSTREAM_MAX_CONCURRENT_INGESTION", configured)

    assert client.post("/events", json=event()).status_code == 200
