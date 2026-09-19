import pytest

from app.delivery_gap import analyze_delivery_gaps


def test_healthy_delivery_cadence():
    report = analyze_delivery_gaps([4, 5, 6, 5], warning_gap_seconds=10, critical_gap_seconds=30)

    assert report.status == "healthy"
    assert report.samples == 5
    assert report.breached_gaps == 0
    assert report.longest_gap_seconds == 6


def test_warning_gap_degrades_stream_health():
    report = analyze_delivery_gaps([5, 12, 6], warning_gap_seconds=10, critical_gap_seconds=30)

    assert report.status == "degraded"
    assert report.breached_gaps == 1
    assert report.longest_gap_seconds == 12


def test_critical_gap_marks_stream_critical():
    report = analyze_delivery_gaps([5, 120, 6])

    assert report.status == "critical"
    assert report.breached_gaps == 1


def test_p95_exposes_tail_delivery_latency():
    gaps = list(range(1, 101))
    report = analyze_delivery_gaps(gaps, warning_gap_seconds=200, critical_gap_seconds=300)

    assert report.p95_gap_seconds == 95
    assert report.longest_gap_seconds == 100


def test_empty_delivery_history_returns_no_data():
    report = analyze_delivery_gaps([])

    assert report.status == "no_data"
    assert report.samples == 0
    assert report.gap_count == 0


@pytest.mark.parametrize("gap", [float("nan"), float("inf"), float("-inf"), -1, True, "5", None])
def test_invalid_interarrival_duration_is_rejected(gap):
    with pytest.raises(ValueError):
        analyze_delivery_gaps([gap])


@pytest.mark.parametrize("warning", [0, -1, float("nan"), float("inf"), True, "30", None])
def test_invalid_warning_threshold_is_rejected(warning):
    with pytest.raises(ValueError):
        analyze_delivery_gaps([5], warning_gap_seconds=warning)


@pytest.mark.parametrize("critical", [0, -1, 30, float("nan"), float("inf"), True, "120", None])
def test_invalid_critical_threshold_is_rejected(critical):
    with pytest.raises(ValueError):
        analyze_delivery_gaps([5], warning_gap_seconds=30, critical_gap_seconds=critical)
