from dataclasses import dataclass
import math


@dataclass(frozen=True)
class DrainTimeReport:
    backlog_events: int
    net_drain_rate_per_second: float
    estimated_drain_seconds: float | None
    status: str


def analyze_drain_time(
    backlog_events: int,
    ingest_rate_per_second: float,
    processing_rate_per_second: float,
    warning_seconds: float = 300.0,
    critical_seconds: float = 900.0,
) -> DrainTimeReport:
    values = (ingest_rate_per_second, processing_rate_per_second, warning_seconds, critical_seconds)
    if isinstance(backlog_events, bool) or not isinstance(backlog_events, int) or backlog_events < 0:
        raise ValueError("backlog_events must be a non-negative integer")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
        raise ValueError("rates and thresholds must be finite numbers")
    if ingest_rate_per_second < 0 or processing_rate_per_second < 0:
        raise ValueError("rates must be non-negative")
    if warning_seconds <= 0 or critical_seconds <= warning_seconds:
        raise ValueError("time thresholds must be positive and increasing")

    net_rate = processing_rate_per_second - ingest_rate_per_second
    if backlog_events == 0:
        return DrainTimeReport(0, round(net_rate, 2), 0.0, "clear")
    if net_rate <= 0:
        return DrainTimeReport(backlog_events, round(net_rate, 2), None, "growing")

    drain_seconds = backlog_events / net_rate
    if drain_seconds >= critical_seconds:
        status = "critical"
    elif drain_seconds >= warning_seconds:
        status = "degraded"
    else:
        status = "healthy"

    return DrainTimeReport(backlog_events, round(net_rate, 2), round(drain_seconds, 2), status)
