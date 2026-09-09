from datetime import datetime, timedelta, timezone

import pytest

from app.models import TelemetryEvent
from app.processor import EventProcessor


def telemetry(
    source: str,
    metric: str,
    value: float,
    offset_seconds: int,
) -> TelemetryEvent:
    return TelemetryEvent(
        source=source,
        metric=metric,
        value=value,
        timestamp=datetime(2026, 9, 9, tzinfo=timezone.utc)
        + timedelta(seconds=offset_seconds),
    )


def test_batch_processing_summarizes_acceptance_anomalies_and_duplicates() -> None:
    processor = EventProcessor()
    duplicate = telemetry("sensor-a", "temperature", 70.0, 0)
    events = [
        duplicate,
        telemetry("sensor-a", "temperature", 150.0, 1),
        telemetry("sensor-b", "pressure", 90.0, 2),
        duplicate,
    ]

    batch = processor.process_many(events)

    assert batch["received"] == 4
    assert batch["accepted"] == 3
    assert batch["duplicates"] == 1
    assert batch["anomalies"] == 1
    assert [result["accepted"] for result in batch["results"]] == [
        True,
        True,
        True,
        False,
    ]


def test_batch_processing_updates_global_stats_and_history_once_per_accepted_event() -> None:
    processor = EventProcessor()
    first = telemetry("sensor-a", "temperature", 150.0, 0)
    events = [
        first,
        telemetry("sensor-b", "voltage", 12.0, 1),
        first,
    ]

    processor.process_many(events)
    stats = processor.stats()

    assert stats["processed"] == 2
    assert stats["anomalies"] == 1
    assert stats["duplicates"] == 1
    assert len(processor.recent_events(limit=10)) == 2


def test_batch_processing_rejects_empty_and_oversized_batches() -> None:
    processor = EventProcessor()

    with pytest.raises(ValueError, match="at least one"):
        processor.process_many([])

    oversized = [
        telemetry("sensor-a", "voltage", 12.0, index)
        for index in range(1001)
    ]
    with pytest.raises(ValueError, match="more than 1000"):
        processor.process_many(oversized)
