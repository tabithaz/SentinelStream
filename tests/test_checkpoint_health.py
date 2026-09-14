from app.checkpoint_health import analyze_checkpoint_health


def test_healthy_checkpoint_progress():
    assert analyze_checkpoint_health([10, 20, 30], [10, 20, 30]).status == "healthy"


def test_checkpoint_lag_marks_degraded():
    report = analyze_checkpoint_health([100, 220], [100, 100])
    assert report.current_lag == 120
    assert report.status == "degraded"


def test_sustained_stall_marks_critical():
    report = analyze_checkpoint_health([10, 20, 30, 40], [5, 5, 5, 5])
    assert report.stalled_intervals == 3
    assert report.status == "critical"


def test_checkpoint_cannot_exceed_producer_offset():
    import pytest

    with pytest.raises(ValueError):
        analyze_checkpoint_health([10], [11])
