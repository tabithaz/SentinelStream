import math
from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryGapReport:
    samples: int
    gap_count: int
    breached_gaps: int
    longest_gap_seconds: float
    p95_gap_seconds: float
    status: str


def _validate_duration(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite non-negative number")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite non-negative number")


def analyze_delivery_gaps(
    interarrival_seconds: list[float],
    warning_gap_seconds: float = 30.0,
    critical_gap_seconds: float = 120.0,
) -> DeliveryGapReport:
    """Classify prolonged gaps between consecutive stream deliveries."""
    _validate_duration(warning_gap_seconds, "warning gap threshold")
    _validate_duration(critical_gap_seconds, "critical gap threshold")
    if warning_gap_seconds == 0 or critical_gap_seconds <= warning_gap_seconds:
        raise ValueError("gap thresholds must be positive and ordered")

    for gap in interarrival_seconds:
        _validate_duration(gap, "interarrival duration")

    if not interarrival_seconds:
        return DeliveryGapReport(0, 0, 0, 0.0, 0.0, "no_data")

    ordered = sorted(interarrival_seconds)
    rank = max(0, math.ceil(0.95 * len(ordered)) - 1)
    longest = ordered[-1]
    p95 = ordered[rank]
    breached = sum(gap >= warning_gap_seconds for gap in interarrival_seconds)

    if longest >= critical_gap_seconds:
        status = "critical"
    elif longest >= warning_gap_seconds:
        status = "degraded"
    else:
        status = "healthy"

    return DeliveryGapReport(
        samples=len(interarrival_seconds) + 1,
        gap_count=len(interarrival_seconds),
        breached_gaps=breached,
        longest_gap_seconds=longest,
        p95_gap_seconds=p95,
        status=status,
    )
