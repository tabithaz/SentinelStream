from dataclasses import dataclass


@dataclass(frozen=True)
class ThroughputTrendReport:
    samples: int
    first_rate: float
    latest_rate: float
    change_percent: float
    declining_intervals: int
    status: str


def analyze_throughput_trend(
    rates_per_second: list[float],
    warning_drop_percent: float = 20.0,
    critical_drop_percent: float = 50.0,
) -> ThroughputTrendReport:
    """Detect sustained loss of processing throughput across observations."""
    if warning_drop_percent < 0 or critical_drop_percent <= warning_drop_percent:
        raise ValueError("thresholds must satisfy 0 <= warning < critical")
    if any(rate < 0 for rate in rates_per_second):
        raise ValueError("throughput rates cannot be negative")
    if not rates_per_second:
        return ThroughputTrendReport(0, 0.0, 0.0, 0.0, 0, "no_data")

    first = rates_per_second[0]
    latest = rates_per_second[-1]
    declining = sum(
        current < previous
        for previous, current in zip(rates_per_second, rates_per_second[1:])
    )

    if first == 0:
        change_percent = 0.0 if latest == 0 else 100.0
        drop_percent = 0.0
    else:
        change_percent = (latest - first) / first * 100.0
        drop_percent = max(0.0, -change_percent)

    sustained_decline = len(rates_per_second) >= 3 and declining == len(rates_per_second) - 1
    if drop_percent >= critical_drop_percent or (sustained_decline and drop_percent >= warning_drop_percent):
        status = "critical"
    elif drop_percent >= warning_drop_percent or declining >= 2:
        status = "degraded"
    else:
        status = "healthy"

    return ThroughputTrendReport(
        samples=len(rates_per_second),
        first_rate=round(first, 2),
        latest_rate=round(latest, 2),
        change_percent=round(change_percent, 2),
        declining_intervals=declining,
        status=status,
    )
