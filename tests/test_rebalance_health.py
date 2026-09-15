import pytest

from app.rebalance_health import analyze_rebalance_health


def test_healthy_without_rebalances():
    report = analyze_rebalance_health([], 300)
    assert report.status == "healthy"
    assert report.paused_percent == 0


def test_healthy_short_rebalances():
    assert analyze_rebalance_health([1.5, 2.0], 300).status == "healthy"


def test_degraded_rebalance_pause():
    report = analyze_rebalance_health([3, 12], 300)
    assert report.status == "degraded"
    assert report.longest_pause_seconds == 12


def test_critical_pause_budget():
    assert analyze_rebalance_health([20, 20, 25], 300).status == "critical"


def test_validation():
    with pytest.raises(ValueError):
        analyze_rebalance_health([1], 0)
    with pytest.raises(ValueError):
        analyze_rebalance_health([-1], 100)
