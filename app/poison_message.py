from dataclasses import dataclass


@dataclass(frozen=True)
class PoisonMessageReport:
    tracked_messages: int
    poison_messages: int
    max_retry_count: int
    poison_rate_percent: float
    status: str


def analyze_poison_messages(
    retry_counts: list[int],
    poison_retry_threshold: int = 5,
    critical_rate_percent: float = 10.0,
) -> PoisonMessageReport:
    """Identify messages repeatedly failing processing and consuming retry capacity."""
    if poison_retry_threshold <= 0 or not 0 < critical_rate_percent <= 100:
        raise ValueError("invalid poison-message thresholds")
    if any(count < 0 for count in retry_counts):
        raise ValueError("retry counts cannot be negative")
    if not retry_counts:
        return PoisonMessageReport(0, 0, 0, 0.0, "no_data")

    poison = sum(count >= poison_retry_threshold for count in retry_counts)
    rate = poison / len(retry_counts) * 100.0

    if rate >= critical_rate_percent:
        status = "critical"
    elif poison:
        status = "degraded"
    else:
        status = "healthy"

    return PoisonMessageReport(
        tracked_messages=len(retry_counts),
        poison_messages=poison,
        max_retry_count=max(retry_counts),
        poison_rate_percent=round(rate, 2),
        status=status,
    )
