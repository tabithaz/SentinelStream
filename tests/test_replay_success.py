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
