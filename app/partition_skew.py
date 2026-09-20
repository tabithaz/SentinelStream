from dataclasses import dataclass
from statistics import mean

@dataclass(frozen=True)
class PartitionSkewReport:
    partitions: int
    total_events: int
    average_events: float
    busiest_partition_events: int
    skew_ratio: float
    status: str

def analyze_partition_skew(event_counts, warning_ratio=1.75, critical_ratio=2.5):
    if warning_ratio <= 1 or critical_ratio <= warning_ratio:
        raise ValueError("thresholds must satisfy 1 < warning < critical")
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in event_counts):
        raise ValueError("event counts must be non-negative integers")
    if not event_counts:
        return PartitionSkewReport(0, 0, 0.0, 0, 0.0, "no_data")
    average = mean(event_counts)
    busiest = max(event_counts)
    ratio = busiest / average if average else 0.0
    status = "critical" if ratio >= critical_ratio else "degraded" if ratio >= warning_ratio else "healthy"
    return PartitionSkewReport(len(event_counts), sum(event_counts), round(average, 2), busiest, round(ratio, 2), status)
