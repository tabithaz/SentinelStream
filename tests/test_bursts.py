import pytest

from app.bursts import analyze_event_bursts


def test_stable_traffic_has_no_bursts():
    result = analyze_event_bursts([10, 11, 9, 10])
    assert result.status == "stable"
    assert result.burst_windows == 0
    assert result.peak_events == 11


def test_intermittent_burst_is_detected():
    result = analyze_event_bursts([5, 5, 5, 5, 30])
    assert result.status == "intermittent"
    assert result.burst_windows == 1
    assert result.burst_rate_percent == 20.0


def test_empty_stream_is_idle():
    assert analyze_event_bursts([]).status == "idle"


def test_invalid_inputs_are_rejected():
    with pytest.raises(ValueError):
        analyze_event_bursts([1, -1, 3])
    with pytest.raises(ValueError):
        analyze_event_bursts([1, 2, 3], multiplier=1.0)
