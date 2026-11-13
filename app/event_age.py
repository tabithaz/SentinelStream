from dataclasses import dataclass
import math


@dataclass(frozen=True)
class EventAgeReport:
    events: int
    median_age_seconds: float
    oldest_age_seconds: float
    stale_events: int
    stale_rate_percent: float
    status: str


def _valid_age(age):
    if isinstance(age, bool) or not isinstance(age, (int, float)) or age < 0:
        return False
    try:
        return math.isfinite(float(age))
    except OverflowError:
        return False


def analyze_event_age(event_ages_seconds: list[float], stale_after_seconds: float = 60.0, critical_rate_percent: float = 20.0) -> EventAgeReport:
    if isinstance(stale_after_seconds, bool) or not isinstance(stale_after_seconds, (int, float)) or (isinstance(stale_after_seconds, float) and not math.isfinite(stale_after_seconds)) or stale_after_seconds <= 0:
        raise ValueError("stale_after_seconds must be a positive finite number")
    if isinstance(critical_rate_percent, bool) or not isinstance(critical_rate_percent, (int, float)) or (isinstance(critical_rate_percent, float) and not math.isfinite(critical_rate_percent)) or not 0 < critical_rate_percent <= 100:
        raise ValueError("critical_rate_percent must be between 0 and 100")
    if any(not _valid_age(age) for age in event_ages_seconds):
        raise ValueError("event ages must be non-negative finite numbers")
    if not event_ages_seconds:
        return EventAgeReport(0, 0.0, 0.0, 0, 0.0, "no_data")

    sorted_ages = sorted(float(age) for age in event_ages_seconds)
    middle = len(sorted_ages) // 2
    if len(sorted_ages) % 2:
        median_age = sorted_ages[middle]
    else:
        lower, upper = sorted_ages[middle - 1:middle + 1]
        median_age = lower + (upper - lower) / 2

    stale = sum(age > stale_after_seconds for age in event_ages_seconds)
    stale_rate = stale / len(event_ages_seconds) * 100.0
    status = "critical" if stale_rate >= critical_rate_percent else "degraded" if stale else "healthy"
    return EventAgeReport(
        events=len(event_ages_seconds),
        median_age_seconds=round(median_age, 2),
        oldest_age_seconds=round(float(max(event_ages_seconds)), 2),
        stale_events=stale,
        stale_rate_percent=round(stale_rate, 2),
        status=status,
    )
