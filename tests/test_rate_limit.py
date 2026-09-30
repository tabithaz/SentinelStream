from fastapi.testclient import TestClient
import pytest

from app import main
from app.processor import EventProcessor
from app.rate_limit import SlidingWindowRateLimiter


client = TestClient(main.app)


def event(second: int) -> dict:
    return {
        "source": "sensor-alpha",
        "metric": "temperature",
        "value": 72.4,
        "timestamp": f"2026-09-30T15:00:{second:02d}Z",
    }


@pytest.fixture(autouse=True)
def configured_limiter(monkeypatch: pytest.MonkeyPatch) -> EventProcessor:
    processor = EventProcessor()
    monkeypatch.setattr(main, "processor", processor)
    monkeypatch.setattr(main, "ingestion_rate_limiter", SlidingWindowRateLimiter())
    monkeypatch.setenv("SENTINELSTREAM_INGEST_RATE_LIMIT", "2")
    return processor


def test_event_ingestion_returns_standard_rate_limit_response(
    configured_limiter: EventProcessor,
) -> None:
    first = client.post("/events", json=event(0))
    second = client.post("/events", json=event(1))
    blocked = client.post("/events", json=event(2))

    assert first.status_code == second.status_code == 200
    assert first.headers["x-ratelimit-limit"] == "2"
    assert first.headers["x-ratelimit-remaining"] == "1"
    assert second.headers["x-ratelimit-remaining"] == "0"
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "event ingestion rate limit exceeded"}
    assert blocked.headers["x-ratelimit-limit"] == "2"
    assert blocked.headers["x-ratelimit-remaining"] == "0"
    assert int(blocked.headers["retry-after"]) >= 1
    assert configured_limiter.stats()["processed"] == 2


def test_api_keys_receive_independent_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENTINELSTREAM_API_KEY", "alpha-secret")
    alpha_headers = {"X-API-Key": "alpha-secret"}

    assert client.post("/events", json=event(0), headers=alpha_headers).status_code == 200
    assert client.post("/events", json=event(1), headers=alpha_headers).status_code == 200
    assert client.post("/events", json=event(2), headers=alpha_headers).status_code == 429

    monkeypatch.setenv("SENTINELSTREAM_API_KEY", "bravo-secret")
    bravo = client.post(
        "/events",
        json=event(3),
        headers={"X-API-Key": "bravo-secret"},
    )
    assert bravo.status_code == 200
    assert bravo.headers["x-ratelimit-remaining"] == "1"


def test_read_endpoints_are_not_rate_limited() -> None:
    for _ in range(4):
        response = client.get("/events/recent")
        assert response.status_code == 200
        assert "x-ratelimit-limit" not in response.headers


def test_disabled_and_invalid_configuration_preserve_existing_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for configured in ("0", "not-a-number"):
        monkeypatch.setenv("SENTINELSTREAM_INGEST_RATE_LIMIT", configured)
        for second in range(3):
            assert client.post("/events", json=event(second + 10)).status_code == 200


def test_limiter_expires_requests_and_bounds_identity_cardinality() -> None:
    limiter = SlidingWindowRateLimiter(window_seconds=10, max_identities=2)

    assert limiter.check("first", limit=1, now=0).allowed is True
    blocked = limiter.check("first", limit=1, now=5)
    assert blocked.allowed is False
    assert blocked.retry_after_seconds == 5
    assert limiter.check("first", limit=1, now=10).allowed is True

    limiter.check("second", limit=1, now=10)
    limiter.check("third", limit=1, now=10)
    assert limiter.identity_count == 2
    assert limiter.check("first", limit=1, now=10).allowed is True
