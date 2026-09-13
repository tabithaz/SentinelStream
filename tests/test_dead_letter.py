import pytest

from app.dead_letter import analyze_dead_letter_health


def test_healthy_when_no_events_are_dead_lettered():
    result = analyze_dead_letter_health(1000, 0, 0, 0)
    assert result.status == "healthy"
    assert result.unresolved_events == 0


def test_degraded_when_small_backlog_remains():
    result = analyze_dead_letter_health(1000, 8, 5, 5)
    assert result.status == "degraded"
    assert result.unresolved_events == 3


def test_critical_when_dead_letter_rate_is_high():
    result = analyze_dead_letter_health(1000, 60, 40, 35)
    assert result.status == "critical"
    assert result.dead_letter_rate == 0.06


def test_invalid_counter_relationships_are_rejected():
    with pytest.raises(ValueError):
        analyze_dead_letter_health(10, 11, 0, 0)
    with pytest.raises(ValueError):
        analyze_dead_letter_health(10, 5, 6, 0)
    with pytest.raises(ValueError):
        analyze_dead_letter_health(10, 5, 4, 5)
