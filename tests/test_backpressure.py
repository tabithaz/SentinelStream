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
    try:
        analyze_backpressure([1], [1], 0)
        assert False
    except ValueError:
        pass
