from statistics import mean


def analyze_latency(latencies_ms: list[float], budget_ms: float) -> dict:
    """Summarize end-to-end processing latency against an operational budget."""
    if not latencies_ms:
        raise ValueError("latencies_ms must contain at least one sample")
    if budget_ms <= 0:
        raise ValueError("budget_ms must be positive")
    if any(value < 0 for value in latencies_ms):
        raise ValueError("latency samples cannot be negative")

    ordered = sorted(float(value) for value in latencies_ms)
    count = len(ordered)
    p95_index = max(0, min(count - 1, int((0.95 * count) + 0.999999) - 1))
    p95 = ordered[p95_index]
    violations = sum(value > budget_ms for value in ordered)
    violation_rate = violations / count

    if p95 <= budget_ms and violation_rate <= 0.05:
        status = "healthy"
    elif p95 <= budget_ms * 1.5 and violation_rate <= 0.20:
        status = "degraded"
    else:
        status = "critical"

    return {
        "samples": count,
        "average_latency_ms": round(mean(ordered), 2),
        "p95_latency_ms": round(p95, 2),
        "max_latency_ms": round(ordered[-1], 2),
        "budget_ms": round(float(budget_ms), 2),
        "budget_violations": violations,
        "violation_rate_percentage": round(violation_rate * 100, 1),
        "status": status,
    }
