import pytest

from app.replay_success import analyze_replay_success


def test_healthy_replay_success():
    report = analyze_replay_success(100, 100)
    assert report.status == "healthy"
    assert report.failed_replays == 0


def test_degraded_replay_success():
    report = analyze_replay_success(100, 97)
    assert report.status == "degraded"
    assert report.success_rate_percent == 97.0


def test_critical_replay_success():
    assert analyze_replay_success(100, 90).status == "critical"


def test_no_replays():
    assert analyze_replay_success(0, 0).status == "no_data"


def test_rejects_inconsistent_counters():
    with pytest.raises(ValueError):
        analyze_replay_success(2, 3)


@pytest.mark.parametrize("attempts,successful", [(True, 1), (1, False), (1.5, 1), (2, 1.5), ("2", 1)])
def test_rejects_non_integer_counters(attempts, successful):
    with pytest.raises(ValueError, match="counters must be integers"):
        analyze_replay_success(attempts, successful)


@pytest.mark.parametrize(
    "warning,critical",
    [(float("nan"), 95.0), (99.0, float("inf")), (True, 95.0), (99.0, "95")],
)
def test_rejects_invalid_threshold_types(warning, critical):
    with pytest.raises(ValueError, match="thresholds must be finite numbers"):
        analyze_replay_success(100, 100, warning, critical)
