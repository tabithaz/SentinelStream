import pytest

from app.backpressure import analyze_backpressure


def test_backpressure_tracks_queue_growth():
    result = analyze_backpressure([100, 120, 130], [100, 100, 90], 100)
    assert result["current_backlog"] == 60
    assert result["peak_backlog"] == 60
    assert result["peak_capacity_utilization"] == 60.0
    assert result["overloaded_windows"] == 2
    assert result["status"] == "degraded"


def test_healthy_stream_drains_work():
    assert analyze_backpressure([50, 50], [60, 50], 100)["status"] == "healthy"


def test_critical_when_queue_nears_capacity():
    assert analyze_backpressure([100, 100], [50, 50], 100)["status"] == "critical"


def test_invalid_capacity_rejected():
    with pytest.raises(ValueError, match="queue_capacity must be a positive integer"):
        analyze_backpressure([1], [1], 0)


@pytest.mark.parametrize("invalid", [True, False, 1.5, "100", None, float("nan"), float("inf"), -1])
def test_invalid_queue_capacity_rejected(invalid):
    with pytest.raises(ValueError, match="queue_capacity must be a positive integer"):
        analyze_backpressure([10], [5], invalid)


@pytest.mark.parametrize("invalid", [True, False, 1.5, "5", None, float("nan"), float("inf"), -1])
@pytest.mark.parametrize("series", ["produced", "processed"])
def test_invalid_event_counts_rejected(invalid, series):
    produced = [10, invalid] if series == "produced" else [10, 20]
    processed = [5, 5] if series == "produced" else [5, invalid]
    with pytest.raises(ValueError, match="event counts must be non-negative integers"):
        analyze_backpressure(produced, processed, 100)


def test_tuple_and_list_samples_are_supported():
    result = analyze_backpressure((10, 20), [5, 10], 100)
    assert result["current_backlog"] == 15
    assert result["peak_backlog"] == 15
    assert result["drain_ratio"] == 0.5
    assert result["status"] == "critical"


def test_mismatched_and_empty_samples_are_rejected():
    for produced, processed in (([], []), ([1], []), ([1], [1, 2])):
        with pytest.raises(ValueError, match="non-empty and equal length"):
            analyze_backpressure(produced, processed, 100)
