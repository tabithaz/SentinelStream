import pytest

from app.event_age import analyze_event_age


def test_empty_stream_returns_no_data():
    assert analyze_event_age([]).status == "no_data"


def test_fresh_events_are_healthy():
    report = analyze_event_age([2, 5, 8, 12])
    assert report.status == "healthy"
    assert report.median_age_seconds == 6.5
    assert report.oldest_age_seconds == 12


def test_isolated_stale_event_is_degraded():
    report = analyze_event_age([5, 10, 15, 80], critical_rate_percent=50)
    assert report.status == "degraded"
    assert report.stale_events == 1
    assert report.stale_rate_percent == 25.0


def test_stale_backlog_is_critical():
    report = analyze_event_age([5, 70, 80, 90])
    assert report.status == "critical"
    assert report.stale_events == 3


@pytest.mark.parametrize("ages", [[-1], [True], ["5"], [float("nan")], [float("inf")], [float("-inf")]])
def test_invalid_event_ages_are_rejected(ages):
    with pytest.raises(ValueError):
        analyze_event_age(ages)


def test_invalid_thresholds_are_rejected():
    with pytest.raises(ValueError):
        analyze_event_age([1], stale_after_seconds=0)
    with pytest.raises(ValueError):
        analyze_event_age([1], critical_rate_percent=101)


@pytest.mark.parametrize("threshold", [0, -1, float("nan"), float("inf"), float("-inf"), True, "60", None])
def test_invalid_stale_thresholds_are_rejected(threshold):
    with pytest.raises(ValueError):
        analyze_event_age([1], stale_after_seconds=threshold)


@pytest.mark.parametrize("threshold", [0, 101, float("nan"), float("inf"), float("-inf"), True, "20", None])
def test_invalid_critical_thresholds_are_rejected(threshold):
    with pytest.raises(ValueError):
        analyze_event_age([1], critical_rate_percent=threshold)


def test_boundary_threshold_is_accepted():
    assert analyze_event_age([60, 61], stale_after_seconds=60, critical_rate_percent=50).status == "critical"
