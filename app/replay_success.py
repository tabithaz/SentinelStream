from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ReplaySuccessReport:
    replay_attempts: int
    successful_replays: int
    failed_replays: int
    success_rate_percent: float
    status: str


def analyze_replay_success(
    replay_attempts: int,
    successful_replays: int,
    warning_percent: float = 99.0,
    critical_percent: float = 95.0,
) -> ReplaySuccessReport:
    if (
        isinstance(replay_attempts, bool)
        or not isinstance(replay_attempts, int)
        or isinstance(successful_replays, bool)
        or not isinstance(successful_replays, int)
    ):
        raise ValueError("replay counters must be integers")
    if replay_attempts < 0 or successful_replays < 0 or successful_replays > replay_attempts:
        raise ValueError("replay counters are inconsistent")

    thresholds = (warning_percent, critical_percent)
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in thresholds):
        raise ValueError("thresholds must be finite numbers")
    if not all(math.isfinite(value) for value in thresholds):
        raise ValueError("thresholds must be finite numbers")
    if not 0 <= critical_percent < warning_percent <= 100:
        raise ValueError("thresholds must satisfy 0 <= critical < warning <= 100")
    if replay_attempts == 0:
        return ReplaySuccessReport(0, 0, 0, 0.0, "no_data")

    failed = replay_attempts - successful_replays
    rate = successful_replays / replay_attempts * 100.0
    if rate >= warning_percent:
        status = "healthy"
    elif rate >= critical_percent:
        status = "degraded"
    else:
        status = "critical"

    return ReplaySuccessReport(
        replay_attempts=replay_attempts,
        successful_replays=successful_replays,
        failed_replays=failed,
        success_rate_percent=round(rate, 2),
        status=status,
    )
