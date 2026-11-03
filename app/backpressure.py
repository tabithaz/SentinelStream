from collections.abc import Sequence

def analyze_backpressure(
    produced: Sequence[int], processed: Sequence[int], queue_capacity: int
) -> dict:
    """Measure queue growth and capacity pressure across event windows."""
    if isinstance(queue_capacity, bool) or not isinstance(queue_capacity, int) or queue_capacity <= 0:
        raise ValueError("queue_capacity must be a positive integer")
    if len(produced) != len(processed) or not produced:
        raise ValueError("produced and processed must be non-empty and equal length")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for samples in (produced, processed)
        for value in samples
    ):
        raise ValueError("event counts must be non-negative integers")

    backlog = 0
    peak_backlog = 0
    overloaded_windows = 0
    total_produced = sum(produced)
    total_processed = sum(processed)

    for incoming, outgoing in zip(produced, processed):
        backlog = max(0, backlog + incoming - outgoing)
        peak_backlog = max(peak_backlog, backlog)
        if incoming > outgoing:
            overloaded_windows += 1

    utilization = round((peak_backlog / queue_capacity) * 100, 1)
    drain_ratio = round(total_processed / total_produced, 3) if total_produced else 1.0

    if peak_backlog * 100 >= 90 * queue_capacity or (total_produced and total_processed * 100 < 75 * total_produced):
        status = "critical"
    elif peak_backlog * 100 >= 60 * queue_capacity or (total_produced and total_processed * 100 < 95 * total_produced):
        status = "degraded"
    else:
        status = "healthy"

    return {
        "current_backlog": backlog,
        "peak_backlog": peak_backlog,
        "peak_capacity_utilization": utilization,
        "drain_ratio": drain_ratio,
        "overloaded_windows": overloaded_windows,
        "status": status,
    }
