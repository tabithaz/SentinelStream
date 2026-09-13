from dataclasses import dataclass


@dataclass(frozen=True)
class RecoveryPlan:
    retry_delay_seconds: float
    shed_load_percent: float
    action: str


def recommend_recovery(
    error_rate: float,
    queue_utilization: float,
    consecutive_failures: int,
) -> RecoveryPlan:
    if not 0 <= error_rate <= 1:
        raise ValueError("error_rate must be between 0 and 1")
    if not 0 <= queue_utilization <= 1:
        raise ValueError("queue_utilization must be between 0 and 1")
    if consecutive_failures < 0:
        raise ValueError("consecutive_failures cannot be negative")

    pressure = max(error_rate, queue_utilization)
    if consecutive_failures >= 5 or pressure >= 0.9:
        return RecoveryPlan(30.0, 50.0, "open_circuit")
    if consecutive_failures >= 3 or pressure >= 0.7:
        return RecoveryPlan(10.0, 25.0, "throttle")
    if consecutive_failures > 0 or pressure >= 0.5:
        return RecoveryPlan(2.0, 10.0, "backoff")
    return RecoveryPlan(0.0, 0.0, "normal")
