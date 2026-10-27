import pytest

from app.throughput import analyze_throughput


def test_analyze_throughput_reports_healthy_stream() -> None:
    result = analyze_throughput([100, 105, 98, 102, 110], target_per_window=100)

    assert result["windows_observed"] == 5
    assert result["total_events"] == 515
    assert result["average_events_per_window"] == 103.0
    assert result["throughput_utilization"] == 1.03
    assert result["under_target_windows"] == 1
    assert result["under_target_rate"] == 0.2
    assert result["health"] == "degraded"


def test_analyze_throughput_marks_half_under_target_as_critical() -> None:
    result = analyze_throughput([50, 100, 80, 110], target_per_window=100)

    assert result["under_target_windows"] == 2
    assert result["under_target_rate"] == 0.5
    assert result["health"] == "critical"


def test_analyze_throughput_handles_empty_history() -> None:
    result = analyze_throughput([], target_per_window=100)

    assert result == {
        "windows_observed": 0,
        "total_events": 0,
        "average_events_per_window": 0.0,
        "target_per_window": 100,
        "throughput_utilization": 0.0,
        "under_target_windows": 0,
        "under_target_rate": 0.0,
        "health": "healthy",
    }


def test_analyze_throughput_rejects_invalid_input() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        analyze_throughput([1, 2], target_per_window=0)

    with pytest.raises(ValueError, match="non-negative"):
        analyze_throughput([1, -1], target_per_window=10)

@pytest.mark.parametrize("target", [False, True, 1.5, "10", None, float("nan"), float("inf")])
def test_analyze_throughput_rejects_noninteger_target(target) -> None:
    with pytest.raises(ValueError, match="integer greater than zero"):
        analyze_throughput([1, 2], target_per_window=target)


@pytest.mark.parametrize("count", [False, True, 1.5, "10", None, float("nan"), float("inf")])
def test_analyze_throughput_rejects_noninteger_window_count(count) -> None:
    with pytest.raises(ValueError, match="non-negative integers"):
        analyze_throughput([1, count], target_per_window=10)


def test_analyze_throughput_allows_zero_and_target_boundary() -> None:
    result = analyze_throughput([0, 10, 11], target_per_window=10)

    assert result["total_events"] == 21
    assert result["under_target_windows"] == 1
    assert result["health"] == "degraded"
