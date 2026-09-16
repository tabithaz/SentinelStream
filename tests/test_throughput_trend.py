import pytest

from app.throughput_trend import analyze_throughput_trend


def test_stable_throughput_is_healthy():
    report = analyze_throughput_trend([100.0, 103.0, 101.0, 104.0])

    assert report.status == "healthy"
    assert report.latest_rate == 104.0


def test_material_drop_is_degraded():
    report = analyze_throughput_trend([100.0, 95.0, 78.0])

    assert report.change_percent == -22.0
    assert report.status == "critical"


def test_large_drop_is_critical():
    report = analyze_throughput_trend([200.0, 180.0, 90.0])

    assert report.change_percent == -55.0
    assert report.status == "critical"


def test_non_sustained_warning_drop_is_degraded():
    report = analyze_throughput_trend([100.0, 70.0, 85.0, 75.0])

    assert report.declining_intervals == 2
    assert report.status == "degraded"


def test_empty_series_returns_no_data():
    assert analyze_throughput_trend([]).status == "no_data"


def test_negative_rate_is_rejected():
    with pytest.raises(ValueError):
        analyze_throughput_trend([10.0, -1.0])


@pytest.mark.parametrize("invalid_rate", [float("nan"), float("inf"), float("-inf"), True, "10"])
def test_invalid_rate_is_rejected(invalid_rate):
    with pytest.raises(ValueError, match="throughput rate at index 1 must be a finite number"):
        analyze_throughput_trend([10.0, invalid_rate])


@pytest.mark.parametrize("invalid_threshold", [float("nan"), float("inf"), True, "20"])
def test_invalid_threshold_is_rejected(invalid_threshold):
    with pytest.raises(ValueError, match="warning threshold must be a finite number"):
        analyze_throughput_trend([10.0, 9.0], warning_drop_percent=invalid_threshold)
