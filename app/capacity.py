from datetime import datetime, timedelta

from app.backpressure import analyze_backpressure


def summarize_backpressure(
    events: list[dict],
    window_seconds: int = 60,
    windows: int = 5,
    service_capacity_per_window: int = 100,
    queue_capacity: int = 1000,
    source: str | None = None,
) -> dict:
    if window_seconds <= 0:
        raise ValueError("window_seconds must be greater than zero")
    if windows <= 0:
        raise ValueError("windows must be greater than zero")
    if service_capacity_per_window <= 0:
        raise ValueError("service_capacity_per_window must be greater than zero")
    if queue_capacity <= 0:
        raise ValueError("queue_capacity must be greater than zero")

    relevant = [
        event for event in events if source is None or event["source"] == source
    ]
    counts = [0] * windows
    anchor = None

    if relevant:
        timestamps = [datetime.fromisoformat(event["timestamp"]) for event in relevant]
        anchor = max(timestamps)
        horizon = timedelta(seconds=window_seconds * windows)

        for timestamp in timestamps:
            age = anchor - timestamp
            if age < timedelta(0) or age >= horizon:
                continue

            windows_ago = int(age.total_seconds() // window_seconds)
            index = windows - 1 - windows_ago
            counts[index] += 1

    processed_counts: list[int] = []
    backlog = 0
    for incoming in counts:
        available = backlog + incoming
        processed = min(available, service_capacity_per_window)
        processed_counts.append(processed)
        backlog = available - processed

    analysis = analyze_backpressure(counts, processed_counts, queue_capacity)
    return {
        **analysis,
        "window_seconds": window_seconds,
        "window_counts": counts,
        "processed_counts": processed_counts,
        "service_capacity_per_window": service_capacity_per_window,
        "queue_capacity": queue_capacity,
        "source": source,
        "anchor_timestamp": anchor.isoformat() if anchor is not None else None,
    }
