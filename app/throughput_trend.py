from dataclasses import dataclass
import math
from numbers import Real


@dataclass(frozen=True)
class ThroughputTrendReport:
    samples: int
    first_rate: float
    latest_rate: float
    change_percent: float
    declining_intervals: int
    status: str


def _validate_finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def analyze_throughput_trend(
    rates_per_second: list[float],
    warning_drop_percent: float = 20.0,
    critical_drop_percent: float = 50.0,
) -> ThroughputTrendReport:
    """Detect sustained loss of processing throughput across observations."""
    warning_drop_percent = _validate_finite_number(warning_drop_percent, "warning threshold")
    critical_drop_percent = _validate_finite_number(critical_drop_percent, "critical threshold")
    if warning_drop_percent < 0 or critical_drop_percent <= warning_drop_percent:
        raise ValueError("thresholds must satisfy 0 <= warning < critical")

    rates = [
        _validate_finite_number(rate, f"throughput rate at index {index}")
        for index, rate in enumerate(rates_per_second)
    ]
    if any(rate < 0 for rate in rates):
        raise ValueError("throughput rates cannot be negative")
    if not rates:
        return ThroughputTrendReport(0, 0.0, 0.0, 0.0, 0, "no_data")

    first = rates[0]
    latest = rates[-1]
    declining = sum(
        current < previous
        for previous, current in zip(rates, rates[1:])
    )

    if first == 0:
        change_percent = 0.0 if latest == 0 else 100.0
        drop_percent = 0.0
    else:
        change_percent = (latest - first) / first * 100.0
        drop_percent = max(0.0, -change_percent)

    sustained_decline = len(rates) >= 3 and declining == len(rates) - 1
    if drop_percent >= critical_drop_percent or (sustained_decline and drop_percent >= warning_drop_percent):
        status = "critical"
    elif drop_percent >= warning_drop_percent or declining >= 2:
        status = "degraded"
    else:
        status = "healthy"

    return ThroughputTrendReport(
        samples=len(rates),
        first_rate=round(first, 2),
        latest_rate=round(latest, 2),
        change_percent=round(change_percent, 2),
        declining_intervals=declining,
        status=status,
    )
