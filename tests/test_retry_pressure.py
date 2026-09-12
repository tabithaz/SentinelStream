import pytest

from app.retry_pressure import analyze_retry_pressure


def test_healthy_retry_pressure():
    result = analyze_retry_pressure(1000, 20, 1)
    assert result["status"] == "healthy"
    assert result["retry_rate"] == 0.02


def test_critical_retry_pressure():
    result = analyze_retry_pressure(100, 70, 35)
    assert result["status"] == "critical"
    assert result["pressure_score"] >= 40


def test_zero_attempts_are_safe():
    assert analyze_retry_pressure(0, 0, 0)["status"] == "healthy"


def test_inconsistent_counters_rejected():
    with pytest.raises(ValueError):
        analyze_retry_pressure(10, 11, 0)
