from fastapi.testclient import TestClient
import pytest

from app import main
from app.processor import EventProcessor


client = TestClient(main.app)


def event(second: int = 0) -> dict:
    return {
        "source": "sensor-alpha",
        "metric": "temperature",
        "value": 72.4,
        "timestamp": f"2026-09-29T20:00:{second:02d}Z",
    }


@pytest.fixture(autouse=True)
def secured_processor(monkeypatch: pytest.MonkeyPatch) -> EventProcessor:
    processor = EventProcessor()
    monkeypatch.setattr(main, "processor", processor)
    monkeypatch.setenv("SENTINELSTREAM_API_KEY", "mission-secret")
    return processor


@pytest.mark.parametrize("path", ["/events", "/events/batch", "/events/replay"])
def test_event_writes_require_valid_api_key(
    path: str,
    secured_processor: EventProcessor,
) -> None:
    if path == "/events":
        request = {"json": event()}
    elif path == "/events/batch":
        request = {"json": [event()]}
    else:
        request = {
            "content": "{}\n",
            "headers": {"content-type": "application/x-ndjson"},
        }

    missing = client.post(path, **request)
    wrong_request = {
        **request,
        "headers": {
            **request.get("headers", {}),
            "X-API-Key": "wrong-secret",
        },
    }
    wrong = client.post(path, **wrong_request)

    assert missing.status_code == wrong.status_code == 401
    assert missing.json() == {"detail": "valid X-API-Key required"}
    assert missing.headers["www-authenticate"] == "ApiKey"
    assert secured_processor.stats()["processed"] == 0


def test_valid_api_key_allows_event_ingestion(
    secured_processor: EventProcessor,
) -> None:
    response = client.post(
        "/events",
        json=event(),
        headers={"X-API-Key": "mission-secret"},
    )

    assert response.status_code == 200
    assert response.json()["accepted"] is True
    assert secured_processor.stats()["processed"] == 1


@pytest.mark.parametrize("path", ["/health", "/metrics", "/dashboard", "/events/recent"])
def test_observability_and_read_endpoints_remain_available(path: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
