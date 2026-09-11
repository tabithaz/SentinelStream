import pytest

from app.latency import analyze_latency


def test_healthy_latency_budget():
    result = analyze_latency([40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130, 135], 150)
    assert result["status"] == "healthy"
    assert result["budget_violations"] == 0
    assert result["p95_latency_ms"] == 130.0


def test_degraded_latency_budget():
    result = analyze_latency([80, 90, 100, 110, 120, 130, 140, 145, 160, 170], 150)
    assert result["status"] == "degraded"
    assert result["budget_violations"] == 2


def test_critical_latency_budget():
    result = analyze_latency([100, 120, 180, 240, 300], 150)
    assert result["status"] == "critical"
    assert result["max_latency_ms"] == 300.0


@pytest.mark.parametrize(
    "samples,budget",
    [([], 100), ([1, 2], 0), ([1, -2], 100)],
)
def test_invalid_latency_input(samples, budget):
    with pytest.raises(ValueError):
        analyze_latency(samples, budget)
