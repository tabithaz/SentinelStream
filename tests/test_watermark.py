from app.watermark import analyze_watermark_health


def test_healthy_watermark_progression():
    report = analyze_watermark_health([10, 20, 30], [8, 18, 28])
    assert report.status == "healthy"
    assert report.current_delay_seconds == 2


def test_degraded_when_watermark_stalls():
    report = analyze_watermark_health([10, 20, 30], [8, 8, 25])
    assert report.status == "degraded"
    assert report.stalled_intervals == 1


def test_critical_when_delay_exceeds_limit():
    report = analyze_watermark_health([100, 200], [90, 50])
    assert report.status == "critical"
    assert report.current_delay_seconds == 150


def test_rejects_invalid_timestamps():
    import pytest

    with pytest.raises(ValueError):
        analyze_watermark_health([10], [11])
