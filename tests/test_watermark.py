import pytest

from app.watermark import analyze_watermark_health


def test_healthy_watermark_progression():
    report = analyze_watermark_health([10, 20, 30], [8, 18, 28])
    assert report.status == "healthy"
    assert report.current_delay_seconds == 2


def test_degraded_when_watermark_stalls():
    report = analyze_watermark_health([10, 20, 30], [8, 8, 25])
    assert report.status == "degraded"
    assert report.stalled_intervals == 1
    assert report.consecutive_stalled_intervals == 1


def test_critical_when_delay_exceeds_limit():
    report = analyze_watermark_health([100, 200], [90, 50])
    assert report.status == "critical"
    assert report.current_delay_seconds == 150


def test_critical_only_for_consecutive_stalls():
    report = analyze_watermark_health(
        [10, 20, 30, 40, 50, 60, 70],
        [8, 8, 25, 25, 45, 45, 65],
    )
    assert report.stalled_intervals == 3
    assert report.consecutive_stalled_intervals == 1
    assert report.status == "degraded"

    sustained = analyze_watermark_health([10, 20, 30, 40], [8, 8, 8, 8])
    assert sustained.consecutive_stalled_intervals == 3
    assert sustained.status == "critical"


def test_watermark_regression_is_degraded():
    report = analyze_watermark_health([10, 20, 30], [8, 18, 15])
    assert report.regressions == 1
    assert report.status == "degraded"


def test_rejects_invalid_timestamps():
    with pytest.raises(ValueError):
        analyze_watermark_health([10], [11])
    with pytest.raises(ValueError):
        analyze_watermark_health([20, 10], [10, 9])
