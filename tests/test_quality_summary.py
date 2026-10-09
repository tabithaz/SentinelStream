from fastapi.testclient import TestClient

from app.main import app


def test_quality_summary_returns_valid_contract() -> None:
    response = TestClient(app).get("/events/quality-summary")
    body = response.json()

    assert response.status_code == 200
    assert set(body) == {
        "received",
        "accepted",
        "duplicates",
        "anomalies",
        "acceptance_rate",
        "duplicate_rate",
        "anomaly_rate",
        "quality",
    }
    assert body["received"] >= body["accepted"]
    assert 0.0 <= body["acceptance_rate"] <= 1.0
    assert 0.0 <= body["duplicate_rate"] <= 1.0
    assert 0.0 <= body["anomaly_rate"] <= 1.0
    assert body["quality"] in {"healthy", "degraded", "unreliable"}
