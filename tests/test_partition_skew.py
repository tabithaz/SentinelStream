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
