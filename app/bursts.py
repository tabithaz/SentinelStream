from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BurstAnalysis:
    windows: int
    average_events: float
    peak_events: int
    burst_windows: int
    burst_rate_percent: float
    status: str


def analyze_event_bursts(window_counts: list[int], multiplier: float = 2.0) -> BurstAnalysis:
    if multiplier <= 1.0:
        raise ValueError("multiplier must be greater than 1")
    if any(count < 0 for count in window_counts):
        raise ValueError("window counts must be non-negative")
    if not window_counts:
        return BurstAnalysis(0, 0.0, 0, 0, 0.0, "idle")

    average = sum(window_counts) / len(window_counts)
    threshold = average * multiplier
    burst_windows = sum(1 for count in window_counts if average > 0 and count > threshold)
    burst_rate = (burst_windows / len(window_counts)) * 100.0

    if burst_rate >= 25.0:
        status = "bursty"
    elif burst_windows:
        status = "intermittent"
    else:
        status = "stable"

    return BurstAnalysis(
        windows=len(window_counts),
        average_events=round(average, 1),
        peak_events=max(window_counts),
        burst_windows=burst_windows,
        burst_rate_percent=round(burst_rate, 1),
        status=status,
    )
