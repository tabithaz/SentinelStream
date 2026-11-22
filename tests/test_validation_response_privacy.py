"""Regression coverage for validation-response privacy."""

from fastapi.testclient import TestClient

from app.main import app


def test_invalid_event_does_not_echo_original_payload():
    secret = "private-sensor-token-8675309"
    response = TestClient(app).post(
        "/events",
        json={
            "source": "sensor-alpha",
            "metric": "temperature",
            "value": secret,
            "timestamp": "not-a-timestamp",
        },
    )

    assert response.status_code == 422
    assert secret not in response.text
    assert "not-a-timestamp" not in response.text
    assert response.json()["detail"]
    assert all("input" not in item and "ctx" not in item for item in response.json()["detail"])


def test_invalid_batch_does_not_echo_nested_event_values():
    secret = "private-batch-reading-2468"
    response = TestClient(app).post(
        "/events/batch",
        json=[{
            "source": "sensor-alpha",
            "metric": "temperature",
            "value": secret,
            "timestamp": "invalid-batch-timestamp",
        }],
    )

    assert response.status_code == 422
    assert secret not in response.text
    assert "invalid-batch-timestamp" not in response.text
    assert all(
        not {"input", "ctx", "url"}.intersection(item)
        for item in response.json()["detail"]
    )


def test_invalid_idempotency_header_does_not_echo_header_value():
    secret = "private-idempotency-key-2468"
    response = TestClient(app).post(
        "/events/batch",
        headers={"Idempotency-Key": secret + "!"},
        json=[],
    )

    assert response.status_code == 422
    assert secret not in response.text
    assert all(
        not {"input", "ctx", "url"}.intersection(item)
        for item in response.json()["detail"]
    )


def test_invalid_threshold_metric_key_does_not_echo_user_controlled_location():
    secret = "private-metric-name-13579"
    response = TestClient(app).put(
        "/events/thresholds",
        json={"thresholds": {secret: {"minimum": "invalid", "maximum": 10}}},
    )

    assert response.status_code == 422
    assert secret not in response.text
    assert response.json()["detail"]
    assert any(
        "[redacted]" in item.get("loc", [])
        for item in response.json()["detail"]
    )
    assert all(
        not {"input", "ctx", "url"}.intersection(item)
        for item in response.json()["detail"]
    )
