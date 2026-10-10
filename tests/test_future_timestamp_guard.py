from datetime import datetime, timedelta, timezone
import json

from fastapi.testclient import TestClient
import pytest

from app import main
from app.processor import EventProcessor


client = TestClient(main.app)


def event(seconds_from_now: int) -> dict:
    return {
        "source": "sensor-alpha",
        "metric": "temperature",
        "value": 72.4,
        "timestamp": (
            datetime.now(timezone.utc) + timedelta(seconds=seconds_from_now)
        ).isoformat(),
    }


@pytest.fixture(autouse=True)
def isolated_processor(monkeypatch: pytest.MonkeyPatch) -> EventProcessor:
    processor = EventProcessor()
    monkeypatch.setattr(main, "processor", processor)
    monkeypatch.setenv("SENTINELSTREAM_MAX_FUTURE_SKEW_SECONDS", "60")
    return processor


@pytest.mark.parametrize("path", ["/events", "/events/batch", "/events/replay"])
def test_future_events_are_rejected_before_state_mutation(
    path: str,
    isolated_processor: EventProcessor,
) -> None:
    future = event(120)
    if path == "/events":
        response = client.post(path, json=future)
    elif path == "/events/batch":
        response = client.post(path, json=[event(0), future])
    else:
        response = client.post(
            path,
            content="\n".join(json.dumps(item) for item in [event(0), future]),
            headers={"Content-Type": "application/x-ndjson"},
        )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "event timestamp exceeds maximum future clock skew"
    }
    assert response.headers["x-max-future-skew-seconds"] == "60.0"
    assert isolated_processor.stats()["processed"] == 0


def test_historical_and_in_tolerance_events_are_accepted() -> None:
    assert client.post("/events", json=event(-86400)).status_code == 200
    assert client.post("/events", json=event(30)).status_code == 200


@pytest.mark.parametrize("configured", ["-1", "nan", "inf", "invalid"])
def test_invalid_future_skew_configuration_fails_safe(
    monkeypatch: pytest.MonkeyPatch,
    configured: str,
) -> None:
    monkeypatch.setenv("SENTINELSTREAM_MAX_FUTURE_SKEW_SECONDS", configured)

    assert (
        main._max_future_skew_seconds()
        == main.DEFAULT_MAX_FUTURE_SKEW_SECONDS
    )


def test_zero_disables_future_skew_protection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SENTINELSTREAM_MAX_FUTURE_SKEW_SECONDS", "0")
    assert client.post("/events", json=event(86400)).status_code == 200
