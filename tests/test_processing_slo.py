import pytest

from app.processing_slo import analyze_processing_slo


def test_healthy_when_target_is_met():
    report = analyze_processing_slo([100] * 99 + [700])
    assert report.status == "healthy"
    assert report.attainment_percent == 99.0


def test_degraded_when_budget_is_exceeded_but_not_doubled():
    report = analyze_processing_slo([100] * 98 + [700] * 2, target_percent=99.0)
    assert report.status == "degraded"
    assert report.violations == 2


def test_critical_when_error_budget_is_heavily_consumed():
    report = analyze_processing_slo([100] * 95 + [700] * 5, target_percent=99.0)
    assert report.status == "critical"
    assert report.error_budget_consumed_percent == 500.0


def test_empty_samples_return_no_data():
    assert analyze_processing_slo([]).status == "no_data"


def test_invalid_settings_are_rejected():
    with pytest.raises(ValueError):
        analyze_processing_slo([-1])
    with pytest.raises(ValueError):
        analyze_processing_slo([1], target_percent=100)
