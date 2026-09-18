import pytest

from app.partition_starvation import analyze_partition_starvation


def test_healthy_when_all_partitions_are_active():
    report = analyze_partition_starvation([1, 5, 10, 20])
    assert report.status == "healthy"
    assert report.starved_partitions == 0


def test_degraded_when_small_fraction_is_starved():
    report = analyze_partition_starvation([5, 10, 15, 70, 20], critical_rate_percent=50)
    assert report.status == "degraded"
    assert report.starvation_rate_percent == 20.0


def test_critical_when_starvation_is_widespread():
    report = analyze_partition_starvation([10, 65, 80, 90])
    assert report.status == "critical"
    assert report.starved_partitions == 3
    assert report.largest_idle_seconds == 90


def test_empty_input_returns_no_data():
    assert analyze_partition_starvation([]).status == "no_data"


def test_invalid_values_are_rejected():
    with pytest.raises(ValueError):
        analyze_partition_starvation([-1])
    with pytest.raises(ValueError):
        analyze_partition_starvation([1], starvation_seconds=0)
