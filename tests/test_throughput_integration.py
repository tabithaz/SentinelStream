from datetime import datetime, timedelta, timezone

import pytest

from app.models import TelemetryEvent
from app.processor import EventProcessor


def event(source: str, timestamp: datetime, value: float = 20.0) -> TelemetryEvent:
    return TelemetryEvent(
        source=source,
        metric="temperature",
        value=value,
        timestamp=timestamp,
    )


def test_throughput_summary_bins_recent_events_by_event_time() -> None:
    processor = EventProcessor()
    base = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    processor.process(event("sensor-a", base))
    processor.process(event("sensor-a", base + timedelta(seconds=30), 21.0))
    processor.process(event("sensor-a", base + timedelta(seconds=70), 22.0))
    processor.process(event("sensor-a", base + timedelta(seconds=130), 23.0))
    processor.process(event("sensor-b", base + timedelta(seconds=130), 24.0))

    result = processor.throughput_summary(
        window_seconds=60,
        windows=3,
        target_per_window=2,
    )

    assert result["window_counts"] == [1, 2, 2]
    assert result["total_events"] == 5
    assert result["under_target_windows"] == 1
    assert result["under_target_rate"] == pytest.approx(1 / 3, abs=0.001)
    assert result["health"] == "degraded"
    assert result["anchor_timestamp"] == (base + timedelta(seconds=130)).isoformat()


def test_throughput_summary_can_isolate_a_source() -> None:
    processor = EventProcessor()
    base = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    for seconds in (0, 30, 70, 130):
        processor.process(event("sensor-a", base + timedelta(seconds=seconds), 20.0 + seconds))
    processor.process(event("sensor-b", base + timedelta(seconds=130), 99.0))

    result = processor.throughput_summary(
        window_seconds=60,
        windows=3,
        target_per_window=2,
        source="sensor-a",
    )

    assert result["source"] == "sensor-a"
    assert result["window_counts"] == [1, 2, 1]
    assert result["total_events"] == 4
    assert result["health"] == "critical"


def test_throughput_summary_reports_missing_source_without_fabricating_anchor() -> None:
    processor = EventProcessor()

    result = processor.throughput_summary(
        window_seconds=60,
        windows=3,
        target_per_window=1,
        source="missing",
    )

    assert result["window_counts"] == [0, 0, 0]
    assert result["anchor_timestamp"] is None
    assert result["throughput_utilization"] == 0.0
    assert result["health"] == "critical"


def test_throughput_summary_rejects_invalid_window_configuration() -> None:
    processor = EventProcessor()

    with pytest.raises(ValueError, match="window_seconds"):
        processor.throughput_summary(window_seconds=0)

    with pytest.raises(ValueError, match="windows"):
        processor.throughput_summary(windows=0)

    with pytest.raises(ValueError, match="target_per_window"):
        processor.throughput_summary(target_per_window=0)
