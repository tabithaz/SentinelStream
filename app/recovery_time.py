from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryTimeReport:
    recoveries: int
    average_seconds: float
    slow_recoveries: int
    slow_rate_percent: float
    status: str


def analyze_consumer_recovery(
    recovery_seconds: list[float],
    target_seconds: float = 30.0,
    critical_rate_percent: float = 25.0,
) -> RecoveryTimeReport:
    if target_seconds <= 0:
        raise ValueError("target_seconds must be positive")
    if not 0 < critical_rate_percent <= 100:
        raise ValueError("critical_rate_percent must be between 0 and 100")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 for value in recovery_seconds):
        raise ValueError("recovery durations must be non-negative numbers")
    if not recovery_seconds:
        return RecoveryTimeReport(0, 0.0, 0, 0.0, "no_data")

    slow = sum(value > target_seconds for value in recovery_seconds)
    slow_rate = slow / len(recovery_seconds) * 100.0
    if slow_rate >= critical_rate_percent:
        status = "critical"
    elif slow:
        status = "degraded"
    else:
        status = "healthy"

    return RecoveryTimeReport(
        recoveries=len(recovery_seconds),
        average_seconds=round(sum(recovery_seconds) / len(recovery_seconds), 2),
        slow_recoveries=slow,
        slow_rate_percent=round(slow_rate, 2),
        status=status,
    )
