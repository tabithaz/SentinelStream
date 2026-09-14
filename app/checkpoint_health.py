from dataclasses import dataclass


@dataclass(frozen=True)
class CheckpointHealth:
    current_lag: int
    max_lag: int
    stalled_intervals: int
    status: str


def analyze_checkpoint_health(
    produced_offsets: list[int],
    checkpoint_offsets: list[int],
    warning_lag: int = 100,
    critical_lag: int = 500,
) -> CheckpointHealth:
    if len(produced_offsets) != len(checkpoint_offsets) or not produced_offsets:
        raise ValueError("offset series must be non-empty and equal length")
    if warning_lag < 0 or critical_lag <= warning_lag:
        raise ValueError("invalid lag thresholds")

    lags: list[int] = []
    for produced, checkpoint in zip(produced_offsets, checkpoint_offsets):
        if produced < 0 or checkpoint < 0 or checkpoint > produced:
            raise ValueError("invalid offsets")
        lags.append(produced - checkpoint)

    stalled_intervals = sum(
        1
        for index in range(1, len(checkpoint_offsets))
        if checkpoint_offsets[index] == checkpoint_offsets[index - 1]
        and produced_offsets[index] > produced_offsets[index - 1]
    )

    current_lag = lags[-1]
    max_lag = max(lags)

    if current_lag >= critical_lag or stalled_intervals >= 3:
        status = "critical"
    elif current_lag >= warning_lag or stalled_intervals > 0:
        status = "degraded"
    else:
        status = "healthy"

    return CheckpointHealth(current_lag, max_lag, stalled_intervals, status)
