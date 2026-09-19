import pytest

from app.consumer_utilization import analyze_consumer_utilization


def test_healthy_headroom():
    report = analyze_consumer_utilization([40, 55, 60])
    assert report.status == "healthy"
    assert report.peak_utilization_percent == 60


def test_peak_pressure_is_degraded():
    report = analyze_consumer_utilization([45, 82, 55])
    assert report.status == "degraded"


def test_saturated_consumer_is_critical():
    report = analyze_consumer_utilization([50, 96, 60])
    assert report.saturated_consumers == 1
    assert report.status == "critical"


def test_no_data():
    assert analyze_consumer_utilization([]).status == "no_data"


def test_invalid_utilization():
    with pytest.raises(ValueError):
        analyze_consumer_utilization([101])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), True, "80", None])
def test_non_finite_or_nonnumeric_utilization_is_rejected(value):
    with pytest.raises(ValueError):
        analyze_consumer_utilization([value])


@pytest.mark.parametrize("warning", [float("nan"), float("inf"), True, "80", None])
def test_invalid_warning_threshold_is_rejected(warning):
    with pytest.raises(ValueError):
        analyze_consumer_utilization([50], warning_percent=warning)


@pytest.mark.parametrize("critical", [float("nan"), float("inf"), True, "95", None, 101])
def test_invalid_critical_threshold_is_rejected(critical):
    with pytest.raises(ValueError):
        analyze_consumer_utilization([50], critical_percent=critical)
