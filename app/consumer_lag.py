from collections.abc import Sequence


def analyze_consumer_lag(
    produced_offsets: Sequence[int],
    consumed_offsets: Sequence[int],
    warning_lag: int = 100,
    critical_lag: int = 500,
) -> dict:
    """Evaluate consumer backlog using matched producer and consumer offsets."""
    if warning_lag < 0 or critical_lag <= warning_lag:
        raise ValueError("lag thresholds must be non-negative and increasing")
    if len(produced_offsets) != len(consumed_offsets):
        raise ValueError("producer and consumer samples must have equal length")

    lags: list[int] = []
    for produced, consumed in zip(produced_offsets, consumed_offsets):
        if produced < 0 or consumed < 0:
            raise ValueError("offsets must be non-negative")
        if consumed > produced:
            raise ValueError("consumer offset cannot exceed producer offset")
        lags.append(produced - consumed)

    if not lags:
        return {
            "samples": 0,
            "current_lag": 0,
            "max_lag": 0,
            "average_lag": 0.0,
            "lag_trend": 0,
            "health": "healthy",
        }

    current_lag = lags[-1]
    max_lag = max(lags)
    lag_trend = current_lag - lags[0]

    if current_lag >= critical_lag or max_lag >= critical_lag:
        health = "critical"
    elif current_lag >= warning_lag or max_lag >= warning_lag:
        health = "degraded"
    else:
        health = "healthy"

    return {
        "samples": len(lags),
        "current_lag": current_lag,
        "max_lag": max_lag,
        "average_lag": round(sum(lags) / len(lags), 2),
        "lag_trend": lag_trend,
        "health": health,
    }
