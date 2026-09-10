from app.main import quality_summary


def test_quality_summary_returns_valid_contract() -> None:
    body = quality_summary()

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
