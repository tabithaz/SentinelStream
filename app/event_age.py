from dataclasses import dataclass
from statistics import median


@dataclass(frozen=True)
class EventAgeReport:
    events: int
    median_age_seconds: float
    oldest_age_seconds: float
    stale_events: int
    stale_rate_percent: float
    status: str


def analyze_event_age(event_ages_seconds: list[float], stale_after_seconds: float = 60.0, critical_rate_percent: float = 20.0) -> EventAgeReport:
    if stale_after_seconds <= 0:
        raise ValueError("stale_after_seconds must be positive")
    if not 0 < critical_rate_percent <= 100:
        raise ValueError("critical_rate_percent must be between 0 and 100")
    if any(isinstance(age, bool) or not isinstance(age, (int, float)) or age < 0 for age in event_ages_seconds):
        raise ValueError("event ages must be non-negative numbers")
    if not event_ages_seconds:
        return EventAgeReport(0, 0.0, 0.0, 0, 0.0, "no_data")

    stale = sum(age > stale_after_seconds for age in event_ages_seconds)
    stale_rate = stale / len(event_ages_seconds) * 100.0
    status = "critical" if stale_rate >= critical_rate_percent else "degraded" if stale else "healthy"
    return EventAgeReport(
        events=len(event_ages_seconds),
        median_age_seconds=round(float(median(event_ages_seconds)), 2),
        oldest_age_seconds=round(float(max(event_ages_seconds)), 2),
        stale_events=stale,
        stale_rate_percent=round(stale_rate, 2),
        status=status,
    )
