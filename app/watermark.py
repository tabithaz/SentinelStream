from dataclasses import dataclass


@dataclass(frozen=True)
class WatermarkHealth:
    current_delay_seconds: float
    max_delay_seconds: float
    stalled_intervals: int
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
    for index, (event_time, watermark_time) in enumerate(zip(event_times, watermark_times)):
        if event_time < 0 or watermark_time < 0 or watermark_time > event_time:
            raise ValueError("invalid event or watermark timestamp")
        delays.append(event_time - watermark_time)
        if index > 0 and watermark_time == watermark_times[index - 1] and event_time > event_times[index - 1]:
            stalled += 1

    current = delays[-1]
    maximum = max(delays)
    if current >= critical_delay_seconds or stalled >= 3:
        status = "critical"
    elif current >= warning_delay_seconds or stalled > 0:
        status = "degraded"
    else:
        status = "healthy"

    return WatermarkHealth(
        current_delay_seconds=round(current, 3),
        max_delay_seconds=round(maximum, 3),
        stalled_intervals=stalled,
        status=status,
    )
