from dataclasses import dataclass
from math import isfinite
from numbers import Real


@dataclass(frozen=True)
class RebalanceHealth:
    rebalance_count: int
    total_pause_seconds: float
    longest_pause_seconds: float
    paused_percent: float
    status: str


def analyze_rebalance_health(pause_seconds: list[float], observation_seconds: float) -> RebalanceHealth:
    if not isinstance(observation_seconds, Real) or isinstance(observation_seconds, bool):
        raise ValueError("observation_seconds must be a finite positive number")
    if not isfinite(observation_seconds) or observation_seconds <= 0:
        raise ValueError("observation_seconds must be a finite positive number")

    for pause in pause_seconds:
        if not isinstance(pause, Real) or isinstance(pause, bool) or not isfinite(pause) or pause < 0:
            raise ValueError("rebalance pauses must be finite non-negative numbers")

    total_pause = sum(pause_seconds)
    if total_pause > observation_seconds:
        raise ValueError("total rebalance pause cannot exceed observation window")

    longest_pause = max(pause_seconds, default=0.0)
    paused_percent = total_pause / observation_seconds * 100.0

    if not pause_seconds:
        status = "healthy"
    elif longest_pause >= 30 or paused_percent >= 20:
        status = "critical"
    elif longest_pause >= 10 or paused_percent >= 5:
        status = "degraded"
    else:
        status = "healthy"

    return RebalanceHealth(
        len(pause_seconds), round(total_pause, 2), round(longest_pause, 2), round(paused_percent, 2), status
    )
