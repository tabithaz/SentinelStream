import pytest
from app.partition_skew import analyze_partition_skew

def test_even_distribution_is_healthy():
    report = analyze_partition_skew([100, 110, 95, 105])
    assert report.status == "healthy"
    assert report.total_events == 410

def test_hot_partition_is_degraded():
    assert analyze_partition_skew([10, 10, 10, 30]).status == "degraded"

def test_extreme_hot_partition_is_critical():
    assert analyze_partition_skew([5, 5, 5, 85]).status == "critical"

def test_empty_distribution():
    assert analyze_partition_skew([]).status == "no_data"

@pytest.mark.parametrize("values", [[1, -1], [1, 2.5], [True, 2]])
def test_invalid_partition_counts(values):
    with pytest.raises(ValueError):
        analyze_partition_skew(values)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf"), True, "1.75", None])
@pytest.mark.parametrize("name", ["warning_ratio", "critical_ratio"])
def test_invalid_skew_thresholds_rejected(invalid, name):
    with pytest.raises(ValueError, match="ratio must be a finite number"):
        analyze_partition_skew([1, 1, 10], **{name: invalid})


def test_valid_custom_skew_thresholds():
    report = analyze_partition_skew([1, 1, 8], warning_ratio=1.5, critical_ratio=3.0)
    assert report.status == "degraded"


def test_misordered_thresholds_rejected():
    with pytest.raises(ValueError, match="thresholds must satisfy"):
        analyze_partition_skew([1, 2], warning_ratio=3.0, critical_ratio=2.0)
