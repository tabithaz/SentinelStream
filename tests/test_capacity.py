from app.capacity import summarize_backpressure


def _event(timestamp: str, source: str = "sensor-a") -> dict:
    return {
        "source": source,
        "metric": "temperature",
        "value": 70.0,
        "timestamp": timestamp,
        "anomaly": False,
    }


def test_backpressure_summary_models_queue_growth_from_event_history():
    events = [
        _event("2026-09-12T10:00:00+00:00"),
        _event("2026-09-12T10:01:01+00:00"),
        _event("2026-09-12T10:01:02+00:00"),
    ]

    result = summarize_backpressure(
        events,
        window_seconds=60,
        windows=2,
        service_capacity_per_window=1,
        queue_capacity=2,
    )

    assert result["window_counts"] == [1, 2]
    assert result["processed_counts"] == [1, 1]
    assert result["current_backlog"] == 1
    assert result["peak_backlog"] == 1
    assert result["status"] == "critical"


def test_backpressure_summary_filters_to_requested_source():
    events = [
        _event("2026-09-12T10:00:00+00:00"),
        _event("2026-09-12T10:01:01+00:00"),
        _event("2026-09-12T10:01:02+00:00"),
        _event("2026-09-12T10:01:02+00:00", source="sensor-b"),
    ]

    result = summarize_backpressure(
        events,
        window_seconds=60,
        windows=2,
        service_capacity_per_window=10,
        queue_capacity=20,
        source="sensor-a",
    )

    assert result["window_counts"] == [1, 2]
    assert result["processed_counts"] == [1, 2]
    assert result["source"] == "sensor-a"
    assert result["status"] == "healthy"


def test_backpressure_summary_handles_empty_history():
    result = summarize_backpressure([], windows=3)

    assert result["window_counts"] == [0, 0, 0]
    assert result["processed_counts"] == [0, 0, 0]
    assert result["anchor_timestamp"] is None
    assert result["status"] == "healthy"


def test_backpressure_summary_rejects_invalid_capacity():
    try:
        summarize_backpressure([], service_capacity_per_window=0)
        assert False
    except ValueError:
        pass
