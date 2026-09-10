import pytest

from app.reliability import classify_stream_reliability


def test_reliability_score_for_clean_stream():
    result = classify_stream_reliability(
        anomaly_rate=0.02,
        duplicate_rate=0.01,
        out_of_order_rate=0.0,
    )
    assert result == {"score": 98.7, "status": "reliable"}


def test_reliability_score_for_degraded_stream():
    result = classify_stream_reliability(
        anomaly_rate=0.2,
        duplicate_rate=0.15,
        out_of_order_rate=0.1,
    )
    assert result == {"score": 83.5, "status": "degraded"}


def test_reliability_score_for_unreliable_stream():
    result = classify_stream_reliability(
        anomaly_rate=0.5,
        duplicate_rate=0.35,
        out_of_order_rate=0.3,
    )
    assert result["score"] == 58.5
    assert result["status"] == "unreliable"


def test_reliability_rejects_invalid_rates():
    with pytest.raises(ValueError):
        classify_stream_reliability(
            anomaly_rate=1.1,
            duplicate_rate=0.0,
            out_of_order_rate=0.0,
        )
