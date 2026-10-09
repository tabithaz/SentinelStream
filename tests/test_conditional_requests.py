from fastapi.testclient import TestClient

import app.main as main
from app.processor import EventProcessor


def test_operational_summaries_support_etag_revalidation() -> None:
    main.processor = EventProcessor()
    client = TestClient(main.app)

    for route in (
        "/events/stats",
        "/events/health-summary",
        "/events/quality-summary",
        "/events/reliability",
        "/events/slo",
    ):
        response = client.get(route)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["etag"].startswith('"')

        unchanged = client.get(
            route,
            headers={"If-None-Match": response.headers["etag"]},
        )
        assert unchanged.status_code == 304
        assert unchanged.content == b""
        assert unchanged.headers["etag"] == response.headers["etag"]


def test_etag_changes_after_ingestion_mutates_summary_state() -> None:
    main.processor = EventProcessor()
    client = TestClient(main.app)
    initial = client.get("/events/stats")

    accepted = client.post(
        "/events",
        json={
            "source": "sensor-alpha",
            "metric": "temperature",
            "value": 72.4,
            "timestamp": "2026-10-09T20:00:00Z",
        },
    )
    assert accepted.status_code == 200

    changed = client.get(
        "/events/stats",
        headers={"If-None-Match": initial.headers["etag"]},
    )
    assert changed.status_code == 200
    assert changed.headers["etag"] != initial.headers["etag"]
    assert changed.json()["processed"] == 1
