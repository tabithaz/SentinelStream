import pytest

from app.consumer_lag import analyze_consumer_lag


def test_healthy_consumer_stays_below_warning_threshold():
    result = analyze_consumer_lag([100, 200, 300], [95, 190, 285])
    assert result["health"] == "healthy"
    assert result["current_lag"] == 15
    assert result["max_lag"] == 15


def test_backlog_crossing_warning_threshold_is_degraded():
    result = analyze_consumer_lag([100, 250, 400], [90, 120, 280])
    assert result["health"] == "degraded"
    assert result["max_lag"] == 130
    assert result["lag_trend"] == 110


def test_large_backlog_is_critical():
    result = analyze_consumer_lag([100, 300, 700], [90, 150, 100])
    assert result["health"] == "critical"
    assert result["current_lag"] == 600


def test_invalid_offsets_are_rejected():
    with pytest.raises(ValueError):
        analyze_consumer_lag([10], [11])
    with pytest.raises(ValueError):
        analyze_consumer_lag([10, 20], [5])
