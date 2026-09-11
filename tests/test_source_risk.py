import pytest

from app.source_risk import classify_source_risk


def test_source_risk_weights_anomalies_more_than_ordering():
    result = classify_source_risk(anomaly_rate=0.4, out_of_order_rate=0.1)

    assert result.score == 31.0
    assert result.level == "elevated"


def test_source_risk_marks_high_error_sources_critical():
    result = classify_source_risk(anomaly_rate=0.7, out_of_order_rate=0.3)

    assert result.score == 58.0
    assert result.level == "critical"


def test_source_risk_keeps_clean_sources_normal():
    result = classify_source_risk(anomaly_rate=0.05, out_of_order_rate=0.02)

    assert result.score == 4.1
    assert result.level == "normal"


@pytest.mark.parametrize("anomaly_rate,out_of_order_rate", [(-0.1, 0.0), (0.0, 1.1)])
def test_source_risk_rejects_invalid_rates(anomaly_rate, out_of_order_rate):
    with pytest.raises(ValueError):
        classify_source_risk(anomaly_rate, out_of_order_rate)
