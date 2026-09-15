from dataclasses import dataclass


@dataclass(frozen=True)
class WatermarkHealth:
    current_delay_seconds: float
    max_delay_seconds: float
    stalled_intervals: int
    consecutive_stalled_intervals: int
    regressions: int
    status: str


def analyze_watermark_health(
    event_times: list[float],
    watermark_times: list[float],
    warning_delay_seconds: float = 30.0,
    critical_delay_seconds: float = 120.0,
) -> WatermarkHealth:
    if len(event_times) != len(watermark_times) or not event_times:
        raise ValueError("event and watermark series must be non-empty and equal length")
    if warning_delay_seconds < 0 or critical_delay_seconds <= warning_delay_seconds:
        raise ValueError("invalid delay thresholds")

    delays = []
    stalled = 0
    consecutive_stalled = 0
    longest_stall = 0
    regressions = 0
    for index, (event_time, watermark_time) in enumerate(zip(event_times, watermark_times)):
        if event_time < 0 or watermark_time < 0 or watermark_time > event_time:
            raise ValueError("invalid event or watermark timestamp")
        if index > 0 and event_time < event_times[index - 1]:
            raise ValueError("event timestamps must be non-decreasing")

        delays.append(event_time - watermark_time)
        if index == 0:
            continue

        previous_watermark = watermark_times[index - 1]
        if watermark_time < previous_watermark:
            regressions += 1
            consecutive_stalled = 0
        elif watermark_time == previous_watermark and event_time > event_times[index - 1]:
            stalled += 1
            consecutive_stalled += 1
            longest_stall = max(longest_stall, consecutive_stalled)
        else:
            consecutive_stalled = 0

    current = delays[-1]
    if current >= critical_delay_seconds or longest_stall >= 3:
        status = "critical"
    elif current >= warning_delay_seconds or stalled > 0 or regressions > 0:
        status = "degraded"
    else:
        status = "healthy"

    return WatermarkHealth(
        current_delay_seconds=round(current, 3),
        max_delay_seconds=round(max(delays), 3),
        stalled_intervals=stalled,
        consecutive_stalled_intervals=longest_stall,
        regressions=regressions,
        status=status,
    )
