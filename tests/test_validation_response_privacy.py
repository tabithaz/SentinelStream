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
