from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.main as main
from app.processor import EventProcessor


client = TestClient(main.app)


def isolated_processor(monkeypatch) -> EventProcessor:
    processor = EventProcessor()
    monkeypatch.setattr(main, "processor", processor)
    return processor


def test_thresholds_are_versioned_and_change_anomaly_policy(monkeypatch) -> None:
    isolated_processor(monkeypatch)

    current = client.get("/events/thresholds")
    assert current.status_code == 200
    assert current.headers["etag"] == '"1"'
    assert current.json()["thresholds"]["temperature"] == {
        "minimum": -40.0,
        "maximum": 120.0,
    }

    updated = client.put(
        "/events/thresholds",
        headers={"If-Match": current.headers["etag"]},
        json={
            "thresholds": {
                " Temperature ": {"minimum": 0, "maximum": 70},
            }
        },
    )
    assert updated.status_code == 200
    assert updated.headers["etag"] == '"2"'
    assert updated.json() == {
        "version": 2,
        "thresholds": {"temperature": {"minimum": 0.0, "maximum": 70.0}},
    }

    event = client.post(
        "/events",
        json={
            "source": "sensor-alpha",
            "metric": "temperature",
            "value": 72,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert event.status_code == 200
    assert event.json()["anomaly"] is True


def test_stale_update_is_rejected_without_mutating_configuration(monkeypatch) -> None:
    isolated_processor(monkeypatch)
    payload = {"thresholds": {"voltage": {"minimum": 1, "maximum": 20}}}

    assert client.put(
        "/events/thresholds", headers={"If-Match": '"1"'}, json=payload
    ).status_code == 200
    stale = client.put(
        "/events/thresholds", headers={"If-Match": '"1"'}, json=payload
    )

    assert stale.status_code == 412
    assert stale.headers["etag"] == '"2"'
    assert stale.json()["current_version"] == 2
    assert client.get("/events/thresholds").json()["version"] == 2


def test_threshold_update_requires_and_validates_precondition(monkeypatch) -> None:
    isolated_processor(monkeypatch)
    payload = {"thresholds": {"pressure": {"minimum": 0, "maximum": 10}}}

    missing = client.put("/events/thresholds", json=payload)
    malformed = client.put(
        "/events/thresholds", headers={"If-Match": "1"}, json=payload
    )

    assert missing.status_code == 428
    assert malformed.status_code == 400
    assert client.get("/events/thresholds").json()["version"] == 1


def test_invalid_threshold_sets_are_rejected_atomically(monkeypatch) -> None:
    isolated_processor(monkeypatch)

    for thresholds in (
        {},
        {"temperature": {"minimum": 10, "maximum": 0}},
        {"   ": {"minimum": 0, "maximum": 1}},
        {
            "Temperature": {"minimum": 0, "maximum": 1},
            "temperature": {"minimum": 0, "maximum": 2},
        },
    ):
        response = client.put(
            "/events/thresholds",
            headers={"If-Match": '"1"'},
            json={"thresholds": thresholds},
        )
        assert response.status_code == 422

    assert client.get("/events/thresholds").json()["version"] == 1


def test_threshold_writes_follow_api_key_policy(monkeypatch) -> None:
    isolated_processor(monkeypatch)
    monkeypatch.setenv("SENTINELSTREAM_API_KEY", "mission-secret")
    payload = {"thresholds": {"temperature": {"minimum": 0, "maximum": 80}}}

    denied = client.put(
        "/events/thresholds", headers={"If-Match": '"1"'}, json=payload
    )
    accepted = client.put(
        "/events/thresholds",
        headers={"If-Match": '"1"', "X-API-Key": "mission-secret"},
        json=payload,
    )

    assert denied.status_code == 401
    assert accepted.status_code == 200
