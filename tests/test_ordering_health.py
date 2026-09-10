from datetime import datetime, timedelta, timezone

from app.models import TelemetryEvent
from app.processor import EventProcessor


def event(source: str, second: int) -> TelemetryEvent:
    base = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)
    return TelemetryEvent(
        source=source,
        metric="temperature",
        value=80.0 + second,
        timestamp=base + timedelta(seconds=second),
    )


def test_source_ordering_health_tracks_out_of_order_rate() -> None:
    processor = EventProcessor()
    processor.process(event("vehicle-a", 4))
    processor.process(event("vehicle-a", 1))
    processor.process(event("vehicle-a", 5))
    processor.process(event("vehicle-a", 6))

    source = processor.stats()["sources"]["vehicle-a"]

    assert source["out_of_order"] == 1
    assert source["out_of_order_rate"] == 0.25
    assert source["ordering_health"] == "critical"


def test_ranked_sources_exposes_ordering_health() -> None:
    processor = EventProcessor()
    processor.process(event("vehicle-clean", 1))
    processor.process(event("vehicle-late", 4))
    processor.process(event("vehicle-late", 1))

    ranked = {item["source"]: item for item in processor.ranked_sources()}

    assert ranked["vehicle-clean"]["ordering_health"] == "healthy"
    assert ranked["vehicle-late"]["out_of_order_rate"] == 0.5
    assert ranked["vehicle-late"]["ordering_health"] == "critical"
