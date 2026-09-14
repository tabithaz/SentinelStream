import pytest
from app.partition_skew import analyze_partition_skew


def test_balanced_partitions():
    result = analyze_partition_skew({"p0": 100, "p1": 95, "p2": 105})
    assert result.status == "balanced"
    assert result.hottest_partition == "p2"


def test_balanced_two_partition_stream_is_not_false_positive():
    result = analyze_partition_skew({"p0": 50, "p1": 50})
    assert result.status == "balanced"
    assert result.hottest_share == 0.5
    assert result.imbalance_ratio == 1.0


def test_moderately_uneven_two_partition_stream_remains_balanced():
    result = analyze_partition_skew({"p0": 60, "p1": 40})
    assert result.status == "balanced"
    assert result.imbalance_ratio == 1.2


def test_skewed_partitions():
    result = analyze_partition_skew({"p0": 150, "p1": 75, "p2": 75})
    assert result.status == "skewed"
    assert result.imbalance_ratio == 1.5


def test_critical_hot_partition():
    result = analyze_partition_skew({"p0": 250, "p1": 25, "p2": 25})
    assert result.status == "critical"
    assert result.hottest_share > 0.8


def test_idle_no_data_and_invalid_counts():
    assert analyze_partition_skew({}).status == "no_data"
    assert analyze_partition_skew({"p0": 0, "p1": 0}).status == "idle"
    with pytest.raises(ValueError):
        analyze_partition_skew({"p0": -1})
