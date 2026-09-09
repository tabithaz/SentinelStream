from datetime import datetime, timezone

from app.models import TelemetryEvent
from app.processor import EventProcessor


def event(source: str, value: float, second: int) -> TelemetryEvent:
    return TelemetryEvent(
        source=source,
        metric="temperature",
        value=value,
        timestamp=datetime(2026, 9, 8, 19, 0, second, tzinfo=timezone.utc),
    )


def test_ranked_sources_orders_by_anomaly_rate() -> None:
    processor = EventProcessor()
    processor.process(event("vehicle-a", 150.0, 1))
    processor.process(event("vehicle-a", 80.0, 2))
    processor.process(event("vehicle-b", 150.0, 3))

    ranked = processor.ranked_sources()

    assert [item["source"] for item in ranked] == ["vehicle-b", "vehicle-a"]
    assert ranked[0]["anomaly_rate"] == 1.0
    assert ranked[1]["anomaly_rate"] == 0.5
    assert ranked[0]["health"] == "critical"
    assert ranked[1]["health"] == "critical"


def test_ranked_sources_classifies_source_health() -> None:
    processor = EventProcessor()
    for second, value in enumerate([80.0, 80.0, 80.0, 80.0, 150.0], start=1):
        processor.process(event("vehicle-watch", value, second))
    processor.process(event("vehicle-healthy", 80.0, 10))

    ranked = processor.ranked_sources()
    by_source = {item["source"]: item for item in ranked}

    assert by_source["vehicle-watch"]["anomaly_rate"] == 0.2
    assert by_source["vehicle-watch"]["health"] == "watch"
    assert by_source["vehicle-healthy"]["health"] == "healthy"


def test_ranked_sources_applies_limit() -> None:
    processor = EventProcessor()
    processor.process(event("vehicle-a", 80.0, 1))
    processor.process(event("vehicle-b", 80.0, 2))

    ranked = processor.ranked_sources(limit=1)

    assert len(ranked) == 1


def test_ranked_sources_rejects_invalid_limit() -> None:
    processor = EventProcessor()

    try:
        processor.ranked_sources(limit=0)
    except ValueError as exc:
        assert str(exc) == "limit must be greater than zero"
    else:
        raise AssertionError("expected ValueError")
