from dataclasses import dataclass


@dataclass(frozen=True)
class DuplicateDeliveryReport:
    total_events: int
    unique_events: int
    duplicate_events: int
    duplicate_rate_percent: float
    status: str


def analyze_duplicate_deliveries(
    event_ids: list[str],
    warning_percent: float = 1.0,
    critical_percent: float = 5.0,
) -> DuplicateDeliveryReport:
    if warning_percent < 0 or critical_percent <= warning_percent:
        raise ValueError("thresholds must satisfy 0 <= warning < critical")
    if any(not event_id.strip() for event_id in event_ids):
        raise ValueError("event IDs must not be blank")

    total = len(event_ids)
    if total == 0:
        return DuplicateDeliveryReport(0, 0, 0, 0.0, "no_data")

    unique = len(set(event_ids))
    duplicates = total - unique
    duplicate_rate = duplicates / total * 100.0

    if duplicate_rate < warning_percent:
        status = "healthy"
    elif duplicate_rate < critical_percent:
        status = "degraded"
    else:
        status = "critical"

    return DuplicateDeliveryReport(
        total_events=total,
        unique_events=unique,
        duplicate_events=duplicates,
        duplicate_rate_percent=round(duplicate_rate, 2),
        status=status,
    )
