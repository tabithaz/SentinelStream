from fastapi.testclient import TestClient
import pytest

from app import main
from app.processor import EventProcessor


client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_processor(monkeypatch: pytest.MonkeyPatch) -> EventProcessor:
    processor = EventProcessor()
    monkeypatch.setattr(main, "processor", processor)
    return processor


def event() -> dict:
    return {
        "source": "sensor-alpha",
        "metric": "temperature",
        "value": 72.0,
        "timestamp": "2026-01-13T14:00:00Z",
    }


def test_drain_rejects_new_event_writes_without_mutating_state(
    tmp_path,
    monkeypatch,
    isolated_processor: EventProcessor,
) -> None:
    marker = tmp_path / "draining"
    marker.touch()
    monkeypatch.setenv("SENTINELSTREAM_DRAIN_MARKER", str(marker))

    response = client.post("/events", json=event())

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.json() == {"detail": "service is draining"}
    assert isolated_processor.stats()["processed"] == 0


def test_drain_preserves_read_only_operational_endpoints(tmp_path, monkeypatch) -> None:
    marker = tmp_path / "draining"
    marker.touch()
    monkeypatch.setenv("SENTINELSTREAM_DRAIN_MARKER", str(marker))

    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 200
    assert client.get("/events/stats").status_code == 200


def test_event_writes_resume_when_drain_marker_is_removed(tmp_path, monkeypatch) -> None:
    marker = tmp_path / "draining"
    marker.touch()
    monkeypatch.setenv("SENTINELSTREAM_DRAIN_MARKER", str(marker))
    marker.unlink()

    response = client.post("/events", json=event())

    assert response.status_code == 200
    assert response.json()["accepted"] is True
