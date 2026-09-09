from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.models import TelemetryEvent
from app.processor import EventProcessor


def test_concurrent_duplicate_submissions_are_atomic() -> None:
    processor = EventProcessor()
    telemetry = TelemetryEvent(
        source="sensor-concurrent",
        metric="temperature",
        value=150.0,
        timestamp=datetime.now(timezone.utc),
    )

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(processor.process, [telemetry] * 100))

    accepted = [result for result in results if result["accepted"]]
    duplicates = [result for result in results if result["duplicate"]]
    stats = processor.stats()

    assert len(accepted) == 1
    assert len(duplicates) == 99
    assert stats["processed"] == 1
    assert stats["anomalies"] == 1
    assert stats["duplicates"] == 99
    assert len(processor.recent_events()) == 1


def test_concurrent_unique_submissions_preserve_counts() -> None:
    processor = EventProcessor(history_size=200)
    timestamp = datetime.now(timezone.utc)
    events = [
        TelemetryEvent(
            source=f"sensor-{index % 4}",
            metric="voltage",
            value=float(index),
            timestamp=timestamp,
        )
        for index in range(100)
    ]

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(processor.process, events))

    stats = processor.stats()

    assert all(result["accepted"] for result in results)
    assert stats["processed"] == 100
    assert stats["duplicates"] == 0
    assert sum(source["processed"] for source in stats["sources"].values()) == 100
    assert len(processor.recent_events(limit=200)) == 100
