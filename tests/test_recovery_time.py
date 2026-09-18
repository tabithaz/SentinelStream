import math

import pytest

from app.recovery_time import analyze_consumer_recovery


def test_empty_recovery_history_returns_no_data():
    report = analyze_consumer_recovery([])
    assert report.status == "no_data"
    assert report.p95_seconds == 0.0
    assert report.worst_seconds == 0.0


def test_fast_recoveries_are_healthy():
    report = analyze_consumer_recovery([4, 8, 12, 20])
    assert report.status == "healthy"
    assert report.slow_recoveries == 0
    assert report.average_seconds == 11.0
    assert report.p95_seconds == 20
    assert report.worst_seconds == 20


def test_isolated_slow_recovery_is_degraded():
    report = analyze_consumer_recovery([5, 8, 10, 12, 40], critical_rate_percent=25)
    assert report.status == "degraded"
    assert report.slow_rate_percent == 20.0


def test_repeated_slow_recovery_is_critical():
    report = analyze_consumer_recovery([5, 35, 40, 10])
    assert report.status == "critical"
    assert report.slow_recoveries == 2


def test_p95_surfaces_tail_recovery_latency():
    durations = list(range(1, 101))
    report = analyze_consumer_recovery(durations, target_seconds=200)
    assert report.average_seconds == 50.5
    assert report.p95_seconds == 95
    assert report.worst_seconds == 100


@pytest.mark.parametrize("durations", [[-1], [True], ["10"], [math.nan], [math.inf]])
def test_invalid_recovery_durations_are_rejected(durations):
    with pytest.raises(ValueError):
        analyze_consumer_recovery(durations)


@pytest.mark.parametrize("target", [0, True, math.nan, math.inf])
def test_invalid_target_thresholds_are_rejected(target):
    with pytest.raises(ValueError):
        analyze_consumer_recovery([1], target_seconds=target)


@pytest.mark.parametrize("critical_rate", [0, 101, True, math.nan, math.inf])
def test_invalid_critical_rate_thresholds_are_rejected(critical_rate):
    with pytest.raises(ValueError):
        analyze_consumer_recovery([1], critical_rate_percent=critical_rate)
