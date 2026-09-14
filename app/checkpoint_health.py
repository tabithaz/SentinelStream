from dataclasses import dataclass


@dataclass(frozen=True)
class CheckpointHealth:
    current_lag: int
    max_lag: int
    stalled_intervals: int
    max_consecutive_stalls: int
    checkpoint_regressions: int
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
    stalled_intervals = 0
    consecutive_stalls = 0
    max_consecutive_stalls = 0
    checkpoint_regressions = 0

    previous_produced: int | None = None
    previous_checkpoint: int | None = None

    for produced, checkpoint in zip(produced_offsets, checkpoint_offsets):
        if produced < 0 or checkpoint < 0 or checkpoint > produced:
            raise ValueError("invalid offsets")

        lags.append(produced - checkpoint)

        if previous_checkpoint is not None:
            if checkpoint < previous_checkpoint:
                checkpoint_regressions += 1
                consecutive_stalls = 0
            elif checkpoint == previous_checkpoint and produced > previous_produced:
                stalled_intervals += 1
                consecutive_stalls += 1
                max_consecutive_stalls = max(max_consecutive_stalls, consecutive_stalls)
            else:
                consecutive_stalls = 0

        previous_produced = produced
        previous_checkpoint = checkpoint

    current_lag = lags[-1]
    max_lag = max(lags)

    if current_lag >= critical_lag or max_consecutive_stalls >= 3:
        status = "critical"
    elif (
        current_lag >= warning_lag
        or stalled_intervals > 0
        or checkpoint_regressions > 0
    ):
        status = "degraded"
    else:
        status = "healthy"

    return CheckpointHealth(
        current_lag,
        max_lag,
        stalled_intervals,
        max_consecutive_stalls,
        checkpoint_regressions,
        status,
    )
