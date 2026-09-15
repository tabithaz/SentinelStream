from dataclasses import dataclass


@dataclass(frozen=True)
class IdempotencyReport:
    processed_events: int
    replayed_events: int
    suppressed_replays: int
    expired_replays: int
    suppression_rate_percent: float
    status: str


def analyze_idempotency_window(
    event_ages_seconds: list[float],
    deduplication_window_seconds: float,
    warning_expired_percent: float = 5.0,
    critical_expired_percent: float = 20.0,
) -> IdempotencyReport:
    if deduplication_window_seconds <= 0:
        raise ValueError("deduplication window must be positive")
    if warning_expired_percent < 0 or critical_expired_percent <= warning_expired_percent:
        raise ValueError("invalid expired replay thresholds")
    if any(age < 0 for age in event_ages_seconds):
        raise ValueError("event ages cannot be negative")

    replayed = len(event_ages_seconds)
    if replayed == 0:
        return IdempotencyReport(0, 0, 0, 0, 100.0, "healthy")

    suppressed = sum(age <= deduplication_window_seconds for age in event_ages_seconds)
    expired = replayed - suppressed
    suppression_rate = suppressed / replayed * 100.0
    expired_rate = expired / replayed * 100.0

    if expired_rate < warning_expired_percent:
        status = "healthy"
    elif expired_rate < critical_expired_percent:
        status = "degraded"
    else:
        status = "critical"

    return IdempotencyReport(
        processed_events=replayed,
        replayed_events=replayed,
        suppressed_replays=suppressed,
        expired_replays=expired,
        suppression_rate_percent=round(suppression_rate, 2),
        status=status,
    )
