def analyze_backpressure(produced, processed, queue_capacity):
    if queue_capacity <= 0:
        raise ValueError("queue_capacity must be positive")
    if len(produced) != len(processed) or not produced:
        raise ValueError("produced and processed must be non-empty and equal length")
    if any(v < 0 for v in produced + processed):
        raise ValueError("event counts cannot be negative")

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

    if utilization >= 90 or drain_ratio < 0.75:
        status = "critical"
    elif utilization >= 60 or drain_ratio < 0.95:
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
