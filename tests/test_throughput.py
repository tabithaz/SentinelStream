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
