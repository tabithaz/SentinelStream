from dataclasses import dataclass


@dataclass(frozen=True)
class DeadLetterHealth:
    dead_letter_rate: float
    replay_success_rate: float
    unresolved_events: int
    status: str


def analyze_dead_letter_health(
    processed_events: int,
    dead_letter_events: int,
    replayed_events: int,
    replay_successes: int,
) -> DeadLetterHealth:
    counts = (processed_events, dead_letter_events, replayed_events, replay_successes)
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in counts):
        raise ValueError("event counts must be non-negative integers")
    if dead_letter_events > processed_events:
        raise ValueError("dead_letter_events cannot exceed processed_events")
    if replayed_events > dead_letter_events:
        raise ValueError("replayed_events cannot exceed dead_letter_events")
    if replay_successes > replayed_events:
        raise ValueError("replay_successes cannot exceed replayed_events")

    dead_letter_rate = dead_letter_events / processed_events if processed_events else 0.0
    replay_success_rate = replay_successes / replayed_events if replayed_events else 1.0
    unresolved_events = dead_letter_events - replay_successes

    if dead_letter_rate >= 0.05 or replay_success_rate < 0.7 or unresolved_events >= 100:
        status = "critical"
    elif dead_letter_rate >= 0.01 or replay_success_rate < 0.9 or unresolved_events > 0:
        status = "degraded"
    else:
        status = "healthy"

    return DeadLetterHealth(
        round(dead_letter_rate, 4),
        round(replay_success_rate, 4),
        unresolved_events,
        status,
    )
