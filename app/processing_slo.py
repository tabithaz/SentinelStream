import math
from dataclasses import dataclass
from numbers import Real


@dataclass(frozen=True)
class ProcessingSLOReport:
    processed_events: int
    within_slo: int
    violations: int
    attainment_percent: float
    error_budget_consumed_percent: float
    status: str


def _validate_finite_number(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")


def analyze_processing_slo(
    latency_ms: list[float],
    slo_ms: float = 500.0,
    target_percent: float = 99.0,
) -> ProcessingSLOReport:
    _validate_finite_number(slo_ms, "slo_ms")
    _validate_finite_number(target_percent, "target_percent")
    if slo_ms <= 0:
        raise ValueError("slo_ms must be positive")
    if not 0 < target_percent < 100:
        raise ValueError("target_percent must be between 0 and 100")
    for value in latency_ms:
        _validate_finite_number(value, "latency")
        if value < 0:
            raise ValueError("latency values cannot be negative")
    if not latency_ms:
        return ProcessingSLOReport(0, 0, 0, 0.0, 0.0, "no_data")

    within = sum(value <= slo_ms for value in latency_ms)
    violations = len(latency_ms) - within
    attainment = within / len(latency_ms) * 100.0
    allowed_failure_percent = 100.0 - target_percent
    actual_failure_percent = 100.0 - attainment
    budget_consumed = actual_failure_percent / allowed_failure_percent * 100.0

    if attainment >= target_percent:
        status = "healthy"
    elif budget_consumed <= 200.0:
        status = "degraded"
    else:
        status = "critical"

    return ProcessingSLOReport(
        processed_events=len(latency_ms),
        within_slo=within,
        violations=violations,
        attainment_percent=round(attainment, 2),
        error_budget_consumed_percent=round(budget_consumed, 2),
        status=status,
    )
