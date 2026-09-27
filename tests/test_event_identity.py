from datetime import datetime, timezone

from app.models import TelemetryEvent
from app.processor import EventProcessor


def event(**updates: object) -> TelemetryEvent:
    values: dict[str, object] = {
        "source": "sensor-alpha",
        "metric": "Temperature",
        "value": 72.4,
        "timestamp": datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc),
    }
    values.update(updates)
    return TelemetryEvent(**values)


def test_event_id_is_stable_for_duplicate_delivery() -> None:
    processor = EventProcessor()
    telemetry = event()

    accepted = processor.process(telemetry)
    duplicate = processor.process(telemetry)

    assert len(accepted["event_id"]) == 64
    assert duplicate["event_id"] == accepted["event_id"]
    assert duplicate["duplicate"] is True


def test_event_id_uses_normalized_metric_and_timestamp() -> None:
    first = EventProcessor().process(event())
    equivalent = EventProcessor().process(
        event(
            metric="temperature",
            timestamp=datetime.fromisoformat("2026-09-27T08:00:00-04:00"),
        )
    )

    assert equivalent["event_id"] == first["event_id"]


def test_event_id_distinguishes_event_payloads() -> None:
    processor = EventProcessor()

    first = processor.process(event())
    changed_source = processor.process(event(source="sensor-beta"))
    changed_value = processor.process(event(value=72.5))

    assert len({first["event_id"], changed_source["event_id"], changed_value["event_id"]}) == 3
    assert processor.recent_events()[0]["event_id"] == changed_value["event_id"]
