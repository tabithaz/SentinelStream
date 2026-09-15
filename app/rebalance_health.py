from dataclasses import dataclass


@dataclass(frozen=True)
class RebalanceHealth:
    rebalance_count: int
    total_pause_seconds: float
    longest_pause_seconds: float
    paused_percent: float
    status: str


def analyze_rebalance_health(pause_seconds: list[float], observation_seconds: float) -> RebalanceHealth:
    if observation_seconds <= 0:
        raise ValueError("observation_seconds must be positive")
    if any(pause < 0 for pause in pause_seconds):
        raise ValueError("rebalance pauses cannot be negative")

    total_pause = sum(pause_seconds)
    longest_pause = max(pause_seconds, default=0.0)
    paused_percent = min(100.0, total_pause / observation_seconds * 100.0)

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
