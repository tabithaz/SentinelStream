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


@pytest.mark.parametrize("invalid_results", [[1], [0], ["false"], [None], [True, 0], [False, ""]])
def test_non_boolean_commit_results_are_rejected(invalid_results):
    with pytest.raises(ValueError, match="commit results must be booleans"):
        analyze_offset_commits(invalid_results)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf"), True, "2", None, 10**400])
@pytest.mark.parametrize("name", ["warning_percent", "critical_percent"])
def test_invalid_threshold_types_are_rejected(invalid, name):
    with pytest.raises(ValueError, match=f"{name} must be a finite number"):
        analyze_offset_commits([True], **{name: invalid})


@pytest.mark.parametrize("warning,critical", [(-1, 10), (0, 0), (10, 10), (2, 101), (101, 102)])
def test_out_of_range_thresholds_are_rejected(warning, critical):
    with pytest.raises(ValueError, match="thresholds must satisfy"):
        analyze_offset_commits([False], warning_percent=warning, critical_percent=critical)


def test_exact_critical_boundary_is_critical():
    report = analyze_offset_commits([False, True], warning_percent=0, critical_percent=50)
    assert report.status == "critical"
    assert report.failure_rate_percent == 50.0


def test_all_failed_commits_reach_100_percent_threshold():
    report = analyze_offset_commits([False, False], warning_percent=2, critical_percent=100)
    assert report.status == "critical"
    assert report.failure_rate_percent == 100.0
