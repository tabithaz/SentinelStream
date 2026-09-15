import pytest

from app.duplicate_delivery import analyze_duplicate_deliveries


def test_unique_events_are_healthy():
    report = analyze_duplicate_deliveries(["evt-1", "evt-2", "evt-3"])
    assert report.duplicate_events == 0
    assert report.status == "healthy"


def test_duplicate_rate_can_be_degraded():
    ids = [f"evt-{index}" for index in range(99)] + ["evt-0"]
    report = analyze_duplicate_deliveries(ids)
    assert report.duplicate_rate_percent == 1.0
    assert report.status == "degraded"


def test_heavy_duplication_is_critical():
    report = analyze_duplicate_deliveries(["a", "a", "b", "b"])
    assert report.duplicate_events == 2
    assert report.status == "critical"


def test_empty_stream_returns_no_data():
    assert analyze_duplicate_deliveries([]).status == "no_data"


def test_rejects_blank_ids_and_invalid_thresholds():
    with pytest.raises(ValueError):
        analyze_duplicate_deliveries([" "])
    with pytest.raises(ValueError):
        analyze_duplicate_deliveries(["evt-1"], 5, 5)
