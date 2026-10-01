"""Service-level objective reporting for retained telemetry events."""


def summarize_event_slo(
    events: list[dict],
    *,
    target_percent: float = 99.0,
    window_events: int = 1000,
) -> dict:
    """Measure event reliability and error-budget burn over a bounded window."""
    if not 0 < target_percent <= 100:
        raise ValueError("target_percent must be greater than 0 and at most 100")
    if window_events < 1:
        raise ValueError("window_events must be positive")

    total = len(events)
    bad_events = sum(
        1 for event in events if event["anomaly"] or event["out_of_order"]
    )
    good_events = total - bad_events

    if total == 0:
        return {
            "status": "no_data",
            "target_percent": target_percent,
            "window_events": window_events,
            "events_evaluated": 0,
            "good_events": 0,
            "bad_events": 0,
            "reliability_percent": None,
            "allowed_bad_events": 0.0,
            "remaining_error_budget_events": 0.0,
            "error_budget_consumed_percent": None,
        }

    reliability_percent = good_events / total * 100
    allowed_bad_events = total * (1 - target_percent / 100)
    remaining_budget = max(0.0, allowed_bad_events - bad_events)

    if allowed_bad_events == 0:
        consumed_percent = 0.0 if bad_events == 0 else None
        status = "healthy" if bad_events == 0 else "exhausted"
    else:
        consumed_percent = bad_events / allowed_bad_events * 100
        if consumed_percent >= 100:
            status = "exhausted"
        elif consumed_percent >= 75:
            status = "at_risk"
        else:
            status = "healthy"

    return {
        "status": status,
        "target_percent": target_percent,
        "window_events": window_events,
        "events_evaluated": total,
        "good_events": good_events,
        "bad_events": bad_events,
        "reliability_percent": round(reliability_percent, 3),
        "allowed_bad_events": round(allowed_bad_events, 3),
        "remaining_error_budget_events": round(remaining_budget, 3),
        "error_budget_consumed_percent": (
            round(consumed_percent, 3) if consumed_percent is not None else None
        ),
    }
