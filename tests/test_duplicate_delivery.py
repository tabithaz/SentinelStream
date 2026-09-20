import math

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


@pytest.mark.parametrize("event_ids", [[" "], [None], [123], ["evt-1", False]])
def test_rejects_invalid_event_ids(event_ids):
    with pytest.raises(ValueError, match="non-blank strings"):
        analyze_duplicate_deliveries(event_ids)


@pytest.mark.parametrize(
    ("warning", "critical"),
    [
        (5, 5),
        (-1, 5),
        (math.nan, 5),
        (1, math.inf),
        (True, 5),
        ("1", 5),
    ],
)
def test_rejects_invalid_thresholds(warning, critical):
    with pytest.raises(ValueError):
        analyze_duplicate_deliveries(["evt-1"], warning, critical)
