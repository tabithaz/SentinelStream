from fastapi.testclient import TestClient
import json
import pytest

from app import main
from app.processor import EventProcessor


client = TestClient(main.app)


def event(source: str = "sensor-alpha") -> dict:
    return {
        "source": source,
        "metric": "temperature",
        "value": 72.4,
        "timestamp": "2026-09-30T20:00:00Z",
    }


@pytest.fixture(autouse=True)
def isolated_processor(monkeypatch: pytest.MonkeyPatch) -> EventProcessor:
    processor = EventProcessor()
    monkeypatch.setattr(main, "processor", processor)
    monkeypatch.setenv("SENTINELSTREAM_MAX_INGESTION_BYTES", "180")
    monkeypatch.setenv("SENTINELSTREAM_INGEST_RATE_LIMIT", "0")
    return processor


@pytest.mark.parametrize("path", ["/events", "/events/batch", "/events/replay"])
def test_oversized_event_writes_are_rejected_before_mutation(
    path: str,
    isolated_processor: EventProcessor,
) -> None:
    oversized = event("s" * 150)
    if path == "/events":
        response = client.post(path, json=oversized)
    elif path == "/events/batch":
        response = client.post(path, json=[oversized])
    else:
        response = client.post(
            path,
            content=(json.dumps(oversized) + "\n") * 2,
            headers={"Content-Type": "application/x-ndjson"},
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "event payload exceeds configured byte limit"}
    assert response.headers["x-max-request-bytes"] == "180"
    assert isolated_processor.stats()["processed"] == 0


def test_request_at_limit_reaches_normal_validation(
    monkeypatch: pytest.MonkeyPatch,
    isolated_processor: EventProcessor,
) -> None:
    payload = b"{}"
    monkeypatch.setenv("SENTINELSTREAM_MAX_INGESTION_BYTES", str(len(payload)))

    response = client.post(
        "/events/replay",
        content=payload,
        headers={"Content-Type": "application/x-ndjson"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "replay line 1: invalid telemetry event"
    assert isolated_processor.stats()["processed"] == 0


def test_actual_body_size_is_checked_when_declared_length_is_too_small(
    isolated_processor: EventProcessor,
) -> None:
    response = client.post(
        "/events/replay",
        content=b"x" * 181,
        headers={
            "Content-Type": "application/x-ndjson",
            "Content-Length": "1",
        },
    )

    assert response.status_code == 413
    assert response.headers["x-max-request-bytes"] == "180"
    assert isolated_processor.stats()["processed"] == 0


@pytest.mark.parametrize("configured", ["0", "-1", "invalid"])
def test_invalid_limits_fail_safe_to_default(
    monkeypatch: pytest.MonkeyPatch,
    configured: str,
) -> None:
    monkeypatch.setenv("SENTINELSTREAM_MAX_INGESTION_BYTES", configured)

    assert main._max_ingestion_bytes() == main.DEFAULT_MAX_INGESTION_BYTES


def test_read_endpoints_are_not_subject_to_ingestion_limit() -> None:
    response = client.get("/events/recent", headers={"Content-Length": "999999"})

    assert response.status_code == 200
