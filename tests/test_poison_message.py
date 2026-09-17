import pytest

from app.poison_message import analyze_poison_messages


def test_clean_retry_profile_is_healthy():
    report = analyze_poison_messages([0, 1, 0, 2, 1])
    assert report.poison_messages == 0
    assert report.status == "healthy"


def test_isolated_poison_message_is_degraded():
    report = analyze_poison_messages([0] * 19 + [7])
    assert report.poison_messages == 1
    assert report.poison_rate_percent == 5.0
    assert report.status == "degraded"


def test_high_poison_rate_is_critical():
    report = analyze_poison_messages([0] * 8 + [5, 9])
    assert report.status == "critical"


def test_empty_profile_has_no_data():
    assert analyze_poison_messages([]).status == "no_data"


def test_invalid_retry_count_is_rejected():
    with pytest.raises(ValueError):
        analyze_poison_messages([0, -1])
