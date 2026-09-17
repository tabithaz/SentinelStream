from dataclasses import dataclass


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
    if replay_attempts < 0 or successful_replays < 0 or successful_replays > replay_attempts:
        raise ValueError("replay counters are inconsistent")
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
