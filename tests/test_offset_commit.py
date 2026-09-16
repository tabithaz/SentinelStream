import pytest

from app.offset_commit import analyze_offset_commits


def test_no_commit_data():
    assert analyze_offset_commits([]).status == "no_data"


def test_successful_commits_are_healthy():
    report = analyze_offset_commits([True] * 20)
    assert report.status == "healthy"
    assert report.failed_commits == 0


def test_scattered_failures_are_degraded():
    report = analyze_offset_commits([True] * 48 + [False] + [True])
    assert report.status == "degraded"
    assert report.failure_rate_percent == 2.0


def test_failure_burst_is_critical():
    report = analyze_offset_commits([True, False, False, False, True])
    assert report.status == "critical"
    assert report.longest_failure_run == 3


def test_invalid_thresholds_are_rejected():
    with pytest.raises(ValueError):
        analyze_offset_commits([True], warning_percent=10, critical_percent=5)
