from dataclasses import dataclass


@dataclass(frozen=True)
class PartitionStarvationReport:
    partitions: int
    starved_partitions: int
    starvation_rate_percent: float
    largest_idle_seconds: float
    status: str


def analyze_partition_starvation(
    idle_seconds: list[float],
    starvation_seconds: float = 60.0,
    critical_rate_percent: float = 25.0,
) -> PartitionStarvationReport:
    if starvation_seconds <= 0:
        raise ValueError("starvation_seconds must be positive")
    if not 0 < critical_rate_percent <= 100:
        raise ValueError("critical_rate_percent must be between 0 and 100")
    if any(value < 0 for value in idle_seconds):
        raise ValueError("idle durations cannot be negative")

    if not idle_seconds:
        return PartitionStarvationReport(0, 0, 0.0, 0.0, "no_data")

    starved = sum(value >= starvation_seconds for value in idle_seconds)
    rate = starved / len(idle_seconds) * 100.0

    if rate >= critical_rate_percent:
        status = "critical"
    elif starved:
        status = "degraded"
    else:
        status = "healthy"

    return PartitionStarvationReport(
        partitions=len(idle_seconds),
        starved_partitions=starved,
        starvation_rate_percent=round(rate, 2),
        largest_idle_seconds=round(max(idle_seconds), 2),
        status=status,
    )
