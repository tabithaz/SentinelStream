from dataclasses import dataclass


@dataclass(frozen=True)
class RetryAmplificationReport:
    original_events: int
    retry_attempts: int
    amplification_factor: float
    retry_share_percent: float
    status: str


def analyze_retry_amplification(
    original_events: int,
    retry_attempts: int,
    warning_factor: float = 1.25,
    critical_factor: float = 1.75,
) -> RetryAmplificationReport:
    """Quantify extra processing load caused by retries."""
    if original_events < 0 or retry_attempts < 0:
        raise ValueError("event counts cannot be negative")
    if warning_factor <= 1.0 or critical_factor <= warning_factor:
        raise ValueError("retry thresholds must satisfy 1 < warning < critical")
    if original_events == 0:
        if retry_attempts:
            raise ValueError("retries require at least one original event")
        return RetryAmplificationReport(0, 0, 0.0, 0.0, "no_data")

    processed = original_events + retry_attempts
    factor = processed / original_events
    retry_share = retry_attempts / processed * 100.0

    if factor >= critical_factor:
        status = "critical"
    elif factor >= warning_factor:
        status = "degraded"
    else:
        status = "healthy"

    return RetryAmplificationReport(
        original_events=original_events,
        retry_attempts=retry_attempts,
        amplification_factor=round(factor, 3),
        retry_share_percent=round(retry_share, 2),
        status=status,
    )
