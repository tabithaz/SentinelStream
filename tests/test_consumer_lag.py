import pytest

from app.consumer_lag import analyze_consumer_lag


def test_healthy_consumer_stays_below_warning_threshold():
    result = analyze_consumer_lag([100, 200, 300], [95, 190, 285])
    assert result["health"] == "healthy"
    assert result["current_lag"] == 15
    assert result["max_lag"] == 15
    assert result["reset_detected"] is False


def test_backlog_crossing_warning_threshold_is_degraded():
    result = analyze_consumer_lag([100, 250, 400], [90, 120, 280])
    assert result["health"] == "degraded"
    assert result["max_lag"] == 130
    assert result["lag_trend"] == 110


def test_large_backlog_is_critical():
    result = analyze_consumer_lag([100, 300, 700], [90, 150, 100])
    assert result["health"] == "critical"
    assert result["current_lag"] == 600
    assert result["consumer_resets"] == 1


def test_consumer_reset_degrades_otherwise_healthy_stream():
    result = analyze_consumer_lag([100, 200, 300], [90, 190, 185])
    assert result["max_lag"] == 115
    assert result["consumer_resets"] == 1
    assert result["producer_resets"] == 0
    assert result["reset_detected"] is True
    assert result["health"] == "degraded"


def test_producer_reset_is_reported():
    result = analyze_consumer_lag([100, 200, 150], [90, 190, 145])
    assert result["producer_resets"] == 1
    assert result["consumer_resets"] == 1
    assert result["reset_detected"] is True
    assert result["health"] == "degraded"


def test_empty_samples_have_no_resets():
    result = analyze_consumer_lag([], [])
    assert result["producer_resets"] == 0
    assert result["consumer_resets"] == 0
    assert result["reset_detected"] is False


def test_invalid_offsets_are_rejected():
    with pytest.raises(ValueError):
        analyze_consumer_lag([10], [11])
    with pytest.raises(ValueError):
        analyze_consumer_lag([10, 20], [5])


@pytest.mark.parametrize("invalid", [True, False, 1.5, float("nan"), float("inf"), "10", None])
@pytest.mark.parametrize("position", ["produced", "consumed"])
def test_non_integer_offsets_are_rejected(invalid, position):
    produced = [10, invalid] if position == "produced" else [10, 20]
    consumed = [5, 10] if position == "produced" else [5, invalid]
    with pytest.raises(ValueError, match="offsets must be non-negative integers"):
        analyze_consumer_lag(produced, consumed)


@pytest.mark.parametrize("invalid", [True, False, 1.5, float("nan"), float("inf"), "10", None, -1])
@pytest.mark.parametrize("name", ["warning_lag", "critical_lag"])
def test_invalid_lag_thresholds_are_rejected(invalid, name):
    with pytest.raises(ValueError, match=f"{name} must be a non-negative integer"):
        analyze_consumer_lag([100], [90], **{name: invalid})


def test_custom_threshold_boundaries_and_empty_samples():
    assert analyze_consumer_lag([100], [90], warning_lag=10, critical_lag=20)["health"] == "degraded"
    assert analyze_consumer_lag([100], [80], warning_lag=10, critical_lag=20)["health"] == "critical"
    assert analyze_consumer_lag([], [], warning_lag=0, critical_lag=1)["health"] == "healthy"


def test_equal_thresholds_are_rejected():
    with pytest.raises(ValueError, match="lag thresholds must be non-negative and increasing"):
        analyze_consumer_lag([10], [5], warning_lag=5, critical_lag=5)
