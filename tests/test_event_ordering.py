from datetime import datetime, timezone

from app.models import TelemetryEvent
from app.processor import EventProcessor


def _event(source: str, metric: str, value: float, second: int) -> TelemetryEvent:
    return TelemetryEvent(
        source=source,
        metric=metric,
        value=value,
        timestamp=datetime(2026, 9, 10, 12, 0, second, tzinfo=timezone.utc),
    )


def test_marks_older_event_out_of_order_for_same_stream() -> None:
    processor = EventProcessor()

    first = processor.process(_event("sensor-a", "temperature", 70.0, 10))
    older = processor.process(_event("sensor-a", "temperature", 71.0, 5))

    assert first["out_of_order"] is False
    assert older["out_of_order"] is True
    assert processor.stats()["out_of_order"] == 1
    assert processor.stats()["out_of_order_rate"] == 0.5


def test_order_tracking_is_independent_per_source_and_metric() -> None:
    processor = EventProcessor()
    processor.process(_event("sensor-a", "temperature", 70.0, 10))

    other_source = processor.process(_event("sensor-b", "temperature", 70.0, 5))
    other_metric = processor.process(_event("sensor-a", "pressure", 100.0, 5))

    assert other_source["out_of_order"] is False
    assert other_metric["out_of_order"] is False
    assert processor.stats()["out_of_order"] == 0


def test_duplicate_is_not_counted_as_out_of_order() -> None:
    processor = EventProcessor()
    newer = _event("sensor-a", "temperature", 70.0, 10)
    older = _event("sensor-a", "temperature", 71.0, 5)

    processor.process(newer)
    processor.process(older)
    duplicate = processor.process(older)

    assert duplicate["accepted"] is False
    assert duplicate["duplicate"] is True
    assert processor.stats()["out_of_order"] == 1


def test_batch_reports_out_of_order_count() -> None:
    processor = EventProcessor()

    result = processor.process_many(
        [
            _event("sensor-a", "temperature", 70.0, 10),
            _event("sensor-a", "temperature", 71.0, 5),
            _event("sensor-a", "temperature", 72.0, 12),
        ]
    )

    assert result["accepted"] == 3
    assert result["out_of_order"] == 1
    assert [item["out_of_order"] for item in result["results"]] == [False, True, False]
