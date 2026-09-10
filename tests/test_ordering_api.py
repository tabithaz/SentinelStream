from fastapi.testclient import TestClient

import app.main as main
from app.processor import EventProcessor


def fresh_client() -> TestClient:
    main.processor = EventProcessor()
    return TestClient(main.app)


def test_sources_endpoint_exposes_ordering_health() -> None:
    client = fresh_client()
    events = [
        {"source": "vehicle-a", "metric": "temperature", "value": 80.0, "timestamp": "2026-09-10T18:00:04Z"},
        {"source": "vehicle-a", "metric": "temperature", "value": 81.0, "timestamp": "2026-09-10T18:00:01Z"},
        {"source": "vehicle-a", "metric": "temperature", "value": 82.0, "timestamp": "2026-09-10T18:00:05Z"},
        {"source": "vehicle-a", "metric": "temperature", "value": 83.0, "timestamp": "2026-09-10T18:00:06Z"},
    ]

    response = client.post("/events/batch", json=events)
    assert response.status_code == 200

    response = client.get("/events/sources")
    assert response.status_code == 200
    source = response.json()[0]
    assert source["source"] == "vehicle-a"
    assert source["processed"] == 4
    assert source["out_of_order"] == 1
    assert source["out_of_order_rate"] == 0.25
    assert source["ordering_health"] == "critical"


def test_batch_and_stats_preserve_ordering_counts() -> None:
    client = fresh_client()
    events = [
        {"source": "vehicle-a", "metric": "pressure", "value": 100.0, "timestamp": "2026-09-10T18:00:03Z"},
        {"source": "vehicle-a", "metric": "pressure", "value": 101.0, "timestamp": "2026-09-10T18:00:02Z"},
        {"source": "vehicle-b", "metric": "pressure", "value": 102.0, "timestamp": "2026-09-10T18:00:01Z"},
    ]

    response = client.post("/events/batch", json=events)
    assert response.status_code == 200
    assert response.json()["out_of_order"] == 1

    stats = client.get("/events/stats")
    assert stats.status_code == 200
    assert stats.json()["processed"] == 3
    assert stats.json()["out_of_order"] == 1
    assert stats.json()["out_of_order_rate"] == 1 / 3


def test_duplicate_replay_does_not_inflate_ordering_health() -> None:
    client = fresh_client()
    newest = {
        "source": "vehicle-a",
        "metric": "voltage",
        "value": 12.0,
        "timestamp": "2026-09-10T18:00:05Z",
    }
    late = {
        "source": "vehicle-a",
        "metric": "voltage",
        "value": 11.0,
        "timestamp": "2026-09-10T18:00:01Z",
    }

    assert client.post("/events", json=newest).status_code == 200
    assert client.post("/events", json=late).status_code == 200
    replay = client.post("/events", json=late)

    assert replay.status_code == 200
    assert replay.json()["duplicate"] is True

    source = client.get("/events/sources").json()[0]
    assert source["processed"] == 2
    assert source["out_of_order"] == 1
    assert source["out_of_order_rate"] == 0.5
    assert source["ordering_health"] == "critical"

    stats = client.get("/events/stats").json()
    assert stats["duplicates"] == 1
    assert stats["out_of_order"] == 1
