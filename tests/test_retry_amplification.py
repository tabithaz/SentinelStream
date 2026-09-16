import pytest

from app.retry_amplification import analyze_retry_amplification


def test_healthy_retry_load():
    report = analyze_retry_amplification(1000, 50)
    assert report.status == "healthy"
    assert report.amplification_factor == 1.05


def test_degraded_retry_load():
    report = analyze_retry_amplification(100, 30)
    assert report.status == "degraded"
    assert report.retry_share_percent == 23.08


def test_critical_retry_load():
    assert analyze_retry_amplification(100, 80).status == "critical"


def test_empty_stream():
    assert analyze_retry_amplification(0, 0).status == "no_data"


def test_retries_without_original_events_are_invalid():
    with pytest.raises(ValueError):
        analyze_retry_amplification(0, 1)


def test_threshold_validation():
    with pytest.raises(ValueError):
        analyze_retry_amplification(10, 1, warning_factor=1.5, critical_factor=1.4)


@pytest.mark.parametrize(
    "original_events,retry_attempts",
    [
        (True, 1),
        (10.5, 1),
        ("10", 1),
        (10, False),
        (10, 1.5),
    ],
)
def test_event_counts_require_integers(original_events, retry_attempts):
    with pytest.raises(ValueError):
        analyze_retry_amplification(original_events, retry_attempts)


@pytest.mark.parametrize(
    "warning_factor,critical_factor",
    [
        (float("nan"), 1.75),
        (float("inf"), 1.75),
        (1.25, float("nan")),
        (1.25, float("inf")),
        (True, 1.75),
        (1.25, "1.75"),
    ],
)
def test_thresholds_require_finite_numbers(warning_factor, critical_factor):
    with pytest.raises(ValueError):
        analyze_retry_amplification(
            10,
            1,
            warning_factor=warning_factor,
            critical_factor=critical_factor,
        )
