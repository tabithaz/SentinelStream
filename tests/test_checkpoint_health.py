import pytest

from app.checkpoint_health import analyze_checkpoint_health


def test_healthy_checkpoint_progress():
    report = analyze_checkpoint_health([10, 20, 30], [10, 20, 30])
    assert report.max_consecutive_stalls == 0
    assert report.checkpoint_regressions == 0
    assert report.status == "healthy"


def test_checkpoint_lag_marks_degraded():
    report = analyze_checkpoint_health([100, 220], [100, 100])
    assert report.current_lag == 120
    assert report.status == "degraded"


def test_sustained_stall_marks_critical():
    report = analyze_checkpoint_health([10, 20, 30, 40], [5, 5, 5, 5])
    assert report.stalled_intervals == 3
    assert report.max_consecutive_stalls == 3
    assert report.status == "critical"


def test_nonconsecutive_stalls_do_not_mark_critical():
    report = analyze_checkpoint_health(
        [10, 20, 30, 40, 50, 60, 70],
        [5, 5, 15, 15, 25, 25, 35],
        warning_lag=100,
        critical_lag=500,
    )

    assert report.stalled_intervals == 3
    assert report.max_consecutive_stalls == 1
    assert report.status == "degraded"


def test_checkpoint_regression_is_reported_and_degraded():
    report = analyze_checkpoint_health([10, 20, 30], [8, 15, 12])

    assert report.checkpoint_regressions == 1
    assert report.max_consecutive_stalls == 0
    assert report.status == "degraded"


def test_checkpoint_cannot_exceed_producer_offset():
    with pytest.raises(ValueError):
        analyze_checkpoint_health([10], [11])
