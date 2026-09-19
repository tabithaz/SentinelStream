import pytest

from app.drain_time import analyze_drain_time


def test_reports_clear_backlog():
    report = analyze_drain_time(0, 100.0, 120.0)
    assert report.estimated_drain_seconds == 0.0
    assert report.status == "clear"


def test_reports_healthy_drain_time():
    report = analyze_drain_time(1000, 100.0, 110.0)
    assert report.net_drain_rate_per_second == 10.0
    assert report.estimated_drain_seconds == 100.0
    assert report.status == "healthy"


def test_reports_degraded_and_critical_drain_times():
    assert analyze_drain_time(4000, 100.0, 110.0).status == "degraded"
    assert analyze_drain_time(10000, 100.0, 110.0).status == "critical"


def test_reports_growing_when_processing_cannot_catch_up():
    report = analyze_drain_time(1000, 120.0, 100.0)
    assert report.estimated_drain_seconds is None
    assert report.status == "growing"


@pytest.mark.parametrize(
    "args",
    [(-1, 1.0, 2.0), (True, 1.0, 2.0), (10, -1.0, 2.0), (10, float("inf"), 2.0)],
)
def test_rejects_invalid_inputs(args):
    with pytest.raises(ValueError):
        analyze_drain_time(*args)
