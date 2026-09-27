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


def event(minute: int, *, source: str = "sensor-alpha", value: float = 72.0) -> dict:
    return {
        "source": source,
        "metric": "temperature",
        "value": value + minute,
        "timestamp": f"2026-09-27T12:{minute:02d}:00Z",
    }


def test_event_pages_are_stable_complete_and_non_overlapping() -> None:
    for minute in range(5):
        assert client.post("/events", json=event(minute)).status_code == 200

    first = client.get("/events/page", params={"limit": 2})
    second = client.get(
        "/events/page",
        params={"limit": 2, "cursor": first.json()["next_cursor"]},
    )
    third = client.get(
        "/events/page",
        params={"limit": 2, "cursor": second.json()["next_cursor"]},
    )

    pages = [first.json(), second.json(), third.json()]
    assert [[item["value"] for item in page["events"]] for page in pages] == [
        [76.0, 75.0], [74.0, 73.0], [72.0],
    ]
    ids = [item["event_id"] for page in pages for item in page["events"]]
    assert len(ids) == len(set(ids)) == 5
    assert [page["has_more"] for page in pages] == [True, True, False]
    assert third.json()["next_cursor"] is None


def test_event_pages_support_filters() -> None:
    client.post("/events", json=event(0, source="sensor-alpha"))
    client.post("/events", json=event(1, source="sensor-beta", value=149.0))
    client.post("/events", json=event(2, source="sensor-beta"))

    response = client.get(
        "/events/page",
        params={"source": "sensor-beta", "anomalies_only": "true"},
    )

    assert response.status_code == 200
    assert len(response.json()["events"]) == 1
    assert response.json()["events"][0]["source"] == "sensor-beta"
    assert response.json()["events"][0]["anomaly"] is True


def test_event_page_rejects_invalid_and_missing_cursors() -> None:
    invalid = client.get("/events/page", params={"cursor": "not-an-event-id"})
    missing = client.get("/events/page", params={"cursor": "0" * 64})

    assert invalid.status_code == 422
    assert missing.status_code == 404
    assert missing.json()["detail"] == "cursor not found in retained history"


def test_event_page_reports_evicted_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "processor", EventProcessor(history_size=2))
    first = client.post("/events", json=event(0)).json()
    client.post("/events", json=event(1))
    client.post("/events", json=event(2))

    response = client.get("/events/page", params={"cursor": first["event_id"]})

    assert response.status_code == 404
