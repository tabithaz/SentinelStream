from dataclasses import dataclass
import math
from numbers import Real


@dataclass(frozen=True)
class PartitionStarvationReport:
    partitions: int
    starved_partitions: int
    starvation_rate_percent: float
    largest_idle_seconds: float
    status: str


def _validate_finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        raise ValueError(f"{name} must be a finite number")
    return numeric_value


def analyze_partition_starvation(
    idle_seconds: list[float],
    starvation_seconds: float = 60.0,
    critical_rate_percent: float = 25.0,
) -> PartitionStarvationReport:
    starvation_seconds = _validate_finite_number(starvation_seconds, "starvation_seconds")
    critical_rate_percent = _validate_finite_number(
        critical_rate_percent, "critical_rate_percent"
    )
    if starvation_seconds <= 0:
        raise ValueError("starvation_seconds must be positive")
    if not 0 < critical_rate_percent <= 100:
        raise ValueError("critical_rate_percent must be between 0 and 100")

    validated_idle_seconds = [
        _validate_finite_number(value, "idle duration") for value in idle_seconds
    ]
    if any(value < 0 for value in validated_idle_seconds):
        raise ValueError("idle durations cannot be negative")

    if not validated_idle_seconds:
        return PartitionStarvationReport(0, 0, 0.0, 0.0, "no_data")

    starved = sum(value >= starvation_seconds for value in validated_idle_seconds)
    rate = starved / len(validated_idle_seconds) * 100.0

    if rate >= critical_rate_percent:
        status = "critical"
    elif starved:
        status = "degraded"
    else:
        status = "healthy"

    return PartitionStarvationReport(
        partitions=len(validated_idle_seconds),
        starved_partitions=starved,
        starvation_rate_percent=round(rate, 2),
        largest_idle_seconds=round(max(validated_idle_seconds), 2),
        status=status,
    )
