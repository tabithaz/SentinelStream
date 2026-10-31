from collections.abc import Sequence


def _require_non_negative_integer(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def analyze_consumer_lag(
    produced_offsets: Sequence[int],
    consumed_offsets: Sequence[int],
    warning_lag: int = 100,
    critical_lag: int = 500,
) -> dict:
    """Evaluate consumer backlog and detect producer or consumer offset resets."""
    _require_non_negative_integer(warning_lag, "warning_lag")
    _require_non_negative_integer(critical_lag, "critical_lag")
    if critical_lag <= warning_lag:
        raise ValueError("lag thresholds must be non-negative and increasing")
    if len(produced_offsets) != len(consumed_offsets):
        raise ValueError("producer and consumer samples must have equal length")

    lags: list[int] = []
    producer_resets = 0
    consumer_resets = 0
    previous_produced: int | None = None
    previous_consumed: int | None = None

    for produced, consumed in zip(produced_offsets, consumed_offsets):
        for offset in (produced, consumed):
            if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
                raise ValueError("offsets must be non-negative integers")
        if consumed > produced:
            raise ValueError("consumer offset cannot exceed producer offset")

        if previous_produced is not None and produced < previous_produced:
            producer_resets += 1
        if previous_consumed is not None and consumed < previous_consumed:
            consumer_resets += 1

        lags.append(produced - consumed)
        previous_produced = produced
        previous_consumed = consumed

    reset_detected = producer_resets > 0 or consumer_resets > 0
    if not lags:
        return {
            "samples": 0,
            "current_lag": 0,
            "max_lag": 0,
            "average_lag": 0.0,
            "lag_trend": 0,
            "producer_resets": 0,
            "consumer_resets": 0,
            "reset_detected": False,
            "health": "healthy",
        }

    current_lag = lags[-1]
    max_lag = max(lags)
    lag_trend = current_lag - lags[0]

    if current_lag >= critical_lag or max_lag >= critical_lag:
        health = "critical"
    elif current_lag >= warning_lag or max_lag >= warning_lag or reset_detected:
        health = "degraded"
    else:
        health = "healthy"

    return {
        "samples": len(lags),
        "current_lag": current_lag,
        "max_lag": max_lag,
        "average_lag": round(sum(lags) / len(lags), 2),
        "lag_trend": lag_trend,
        "producer_resets": producer_resets,
        "consumer_resets": consumer_resets,
        "reset_detected": reset_detected,
        "health": health,
    }
