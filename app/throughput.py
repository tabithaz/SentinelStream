from collections.abc import Sequence


def analyze_throughput(
    window_counts: Sequence[int],
    target_per_window: int,
) -> dict:
    """Summarize stream throughput across equal-duration observation windows."""
    if target_per_window <= 0:
        raise ValueError("target_per_window must be greater than zero")
    if any(count < 0 for count in window_counts):
        raise ValueError("window counts must be non-negative")

    windows = len(window_counts)
    total_events = sum(window_counts)
    under_target = sum(1 for count in window_counts if count < target_per_window)
    average = total_events / windows if windows else 0.0
    utilization = average / target_per_window if windows else 0.0
    under_target_rate = under_target / windows if windows else 0.0

    if under_target_rate >= 0.5:
        health = "critical"
    elif under_target_rate >= 0.2:
        health = "degraded"
    else:
        health = "healthy"

    return {
        "windows_observed": windows,
        "total_events": total_events,
        "average_events_per_window": round(average, 2),
        "target_per_window": target_per_window,
        "throughput_utilization": round(utilization, 3),
        "under_target_windows": under_target,
        "under_target_rate": round(under_target_rate, 3),
        "health": health,
    }
