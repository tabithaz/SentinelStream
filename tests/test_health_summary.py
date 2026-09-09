from fastapi.testclient import TestClient

import app.main as main
from app.processor import EventProcessor


def test_health_summary_aggregates_source_health() -> None:
    main.processor = EventProcessor()
    client = TestClient(main.app)

    events = [
        {"source": "alpha", "metric": "temperature", "value": 25.0, "timestamp": "2026-09-09T10:00:00Z"},
        {"source": "alpha", "metric": "temperature", "value": 26.0, "timestamp": "2026-09-09T10:00:01Z"},
        {"source": "bravo", "metric": "temperature", "value": 200.0, "timestamp": "2026-09-09T10:00:02Z"},
        {"source": "bravo", "metric": "temperature", "value": 20.0, "timestamp": "2026-09-09T10:00:03Z"},
        {"source": "charlie", "metric": "pressure", "value": 300.0, "timestamp": "2026-09-09T10:00:04Z"},
    ]
    response = client.post("/events/batch", json=events)
    assert response.status_code == 200

    response = client.get("/events/health-summary")
    assert response.status_code == 200
    assert response.json() == {
        "sources_monitored": 3,
        "healthy_sources": 1,
        "watch_sources": 1,
        "critical_sources": 1,
        "degraded_sources": 2,
        "degraded_share": 2 / 3,
    }


def test_health_summary_handles_no_sources() -> None:
    main.processor = EventProcessor()
    client = TestClient(main.app)

    response = client.get("/events/health-summary")
    assert response.status_code == 200
    assert response.json()["sources_monitored"] == 0
    assert response.json()["degraded_share"] == 0.0
