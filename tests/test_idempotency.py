import pytest

from app.idempotency import analyze_idempotency_window


def test_replays_inside_window_are_suppressed():
    report = analyze_idempotency_window([2, 5, 10], 30)
    assert report.suppressed_replays == 3
    assert report.expired_replays == 0
    assert report.status == "healthy"


def test_expired_replays_are_reported():
    ages = [5] * 19 + [60]
    report = analyze_idempotency_window(ages, 30)
    assert report.expired_replays == 1
    assert report.suppression_rate_percent == 95.0
    assert report.status == "degraded"


def test_many_expired_replays_are_critical():
    report = analyze_idempotency_window([5, 40, 50, 60], 30)
    assert report.status == "critical"


def test_no_replays_is_healthy():
    report = analyze_idempotency_window([], 30)
    assert report.replayed_events == 0
    assert report.status == "healthy"


def test_invalid_settings_are_rejected():
    with pytest.raises(ValueError):
        analyze_idempotency_window([1], 0)
    with pytest.raises(ValueError):
        analyze_idempotency_window([-1], 30)
