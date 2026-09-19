from dataclasses import dataclass


@dataclass(frozen=True)
class ConsumerUtilizationReport:
    consumers: int
    average_utilization_percent: float
    peak_utilization_percent: float
    saturated_consumers: int
    status: str


def analyze_consumer_utilization(
    utilization_percent: list[float],
    warning_percent: float = 80.0,
    critical_percent: float = 95.0,
) -> ConsumerUtilizationReport:
    """Measure whether stream consumers have enough processing headroom."""
    if warning_percent <= 0 or critical_percent <= warning_percent:
        raise ValueError("utilization thresholds must be positive and ordered")
    if any(value < 0 or value > 100 for value in utilization_percent):
        raise ValueError("consumer utilization must be between 0 and 100 percent")

    if not utilization_percent:
        return ConsumerUtilizationReport(0, 0.0, 0.0, 0, "no_data")

    average = sum(utilization_percent) / len(utilization_percent)
    peak = max(utilization_percent)
    saturated = sum(value >= critical_percent for value in utilization_percent)

    if saturated or average >= critical_percent:
        status = "critical"
    elif peak >= warning_percent or average >= warning_percent:
        status = "degraded"
    else:
        status = "healthy"

    return ConsumerUtilizationReport(
        consumers=len(utilization_percent),
        average_utilization_percent=round(average, 2),
        peak_utilization_percent=round(peak, 2),
        saturated_consumers=saturated,
        status=status,
    )
