from datetime import datetime, timedelta, timezone

from app.models import TelemetryEvent
from app.processor import EventProcessor


def _event(timestamp: datetime) -> TelemetryEvent:
    return TelemetryEvent(
        source="sensor-a",
        metric="temperature",
        value=70.0,
        timestamp=timestamp,
    )


def test_naive_timestamp_is_normalized_to_utc() -> None:
    event = _event(datetime(2026, 9, 11, 12, 0, 0))

    assert event.timestamp.tzinfo == timezone.utc
    assert event.timestamp.isoformat() == "2026-09-11T12:00:00+00:00"


def test_aware_timestamp_is_converted_to_utc() -> None:
    eastern = timezone(timedelta(hours=-4))
    event = _event(datetime(2026, 9, 11, 8, 0, 0, tzinfo=eastern))

    assert event.timestamp == datetime(2026, 9, 11, 12, 0, 0, tzinfo=timezone.utc)


def test_equivalent_instants_deduplicate_across_offsets() -> None:
    processor = EventProcessor()
    eastern = timezone(timedelta(hours=-4))

    first = processor.process(_event(datetime(2026, 9, 11, 12, 0, 0, tzinfo=timezone.utc)))
    replay = processor.process(_event(datetime(2026, 9, 11, 8, 0, 0, tzinfo=eastern)))

    assert first["accepted"] is True
    assert replay["accepted"] is False
    assert replay["duplicate"] is True
    assert processor.stats()["duplicates"] == 1


def test_mixed_naive_and_aware_timestamps_support_ordering() -> None:
    processor = EventProcessor()

    processor.process(_event(datetime(2026, 9, 11, 12, 0, 10)))
    older = processor.process(
        _event(datetime(2026, 9, 11, 11, 59, 59, tzinfo=timezone.utc))
    )

    assert older["accepted"] is True
    assert older["out_of_order"] is True
    assert processor.stats()["out_of_order"] == 1
