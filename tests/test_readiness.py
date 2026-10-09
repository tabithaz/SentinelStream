from fastapi.testclient import TestClient

from app import main
from app.models import TelemetryEvent
from app.processor import EventProcessor


def _event(source: str, metric: str) -> TelemetryEvent:
    return TelemetryEvent(
        source=source,
        metric=metric,
        value=1.0,
        timestamp="2026-10-06T20:00:00Z",
    )


def test_readiness_reports_capacity_headroom(monkeypatch) -> None:
    processor = EventProcessor(source_cardinality_limit=10, stream_cardinality_limit=20)
    processor.process(_event("vehicle-a", "temperature"))
    monkeypatch.setattr(main, "processor", processor)

    response = TestClient(main.app).get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "service": "sentinelstream",
        "cardinality_threshold_percent": 90.0,
        "checks": {
            "sources": {
                "ready": True,
                "tracked": 1,
                "limit": 10,
                "utilization_percent": 10.0,
            },
            "streams": {
                "ready": True,
                "tracked": 1,
                "limit": 20,
                "utilization_percent": 5.0,
            },
        },
    }


def test_readiness_fails_closed_at_configured_threshold(monkeypatch) -> None:
    processor = EventProcessor(source_cardinality_limit=2, stream_cardinality_limit=10)
    processor.process(_event("vehicle-a", "temperature"))
    monkeypatch.setattr(main, "processor", processor)
    monkeypatch.setenv("SENTINELSTREAM_READINESS_CARDINALITY_PERCENT", "50")

    response = TestClient(main.app).get("/ready")

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.json()["status"] == "not_ready"
    assert response.json()["checks"]["sources"]["ready"] is False
    assert response.json()["checks"]["streams"]["ready"] is True


def test_readiness_uses_safe_default_for_invalid_configuration(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "processor",
        EventProcessor(source_cardinality_limit=10, stream_cardinality_limit=10),
    )
    monkeypatch.setenv("SENTINELSTREAM_READINESS_CARDINALITY_PERCENT", "not-a-number")

    response = TestClient(main.app).get("/ready")

    assert response.status_code == 200
    assert response.json()["cardinality_threshold_percent"] == 90.0


def test_readiness_fails_while_instance_is_draining(tmp_path, monkeypatch) -> None:
    marker = tmp_path / "draining"
    marker.touch()
    monkeypatch.setenv("SENTINELSTREAM_DRAIN_MARKER", str(marker))

    response = TestClient(main.app).get("/ready")

    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.json() == {
        "status": "not_ready",
        "service": "sentinelstream",
        "reason": "draining",
    }


def test_readiness_ignores_configured_marker_until_it_exists(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(main, "processor", EventProcessor())
    monkeypatch.setenv(
        "SENTINELSTREAM_DRAIN_MARKER",
        str(tmp_path / "not-created"),
    )

    response = TestClient(main.app).get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
