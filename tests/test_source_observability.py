from datetime import datetime, timezone

from app.models import TelemetryEvent
from app.processor import EventProcessor


def make_event(source: str, metric: str, value: float) -> TelemetryEvent:
    return TelemetryEvent(
        source=source,
        metric=metric,
        value=value,
        timestamp=datetime.now(timezone.utc),
    )


def test_stats_include_per_source_counts_and_rates() -> None:
    processor = EventProcessor()
    processor.process(make_event("sensor-a", "temperature", 72.0))
    processor.process(make_event("sensor-a", "temperature", 150.0))
    processor.process(make_event("sensor-b", "pressure", 90.0))

    stats = processor.stats()

    assert stats["sources"]["sensor-a"] == {
        "processed": 2,
        "anomalies": 1,
        "anomaly_rate": 0.5,
        "health": "critical",
        "out_of_order": 0,
        "out_of_order_rate": 0.0,
        "ordering_health": "healthy",
    }
    assert stats["sources"]["sensor-b"] == {
        "processed": 1,
        "anomalies": 0,
        "anomaly_rate": 0.0,
        "health": "healthy",
        "out_of_order": 0,
        "out_of_order_rate": 0.0,
        "ordering_health": "healthy",
    }


def test_recent_events_can_filter_by_source_with_other_filters() -> None:
    processor = EventProcessor()
    processor.process(make_event("sensor-a", "temperature", 150.0))
    processor.process(make_event("sensor-b", "temperature", 160.0))
    processor.process(make_event("sensor-a", "pressure", 90.0))

    recent = processor.recent_events(
        source="sensor-a",
        metric="TEMPERATURE",
        anomalies_only=True,
    )

    assert len(recent) == 1
    assert recent[0]["source"] == "sensor-a"
    assert recent[0]["metric"] == "temperature"
    assert recent[0]["anomaly"] is True


def test_duplicate_events_do_not_inflate_source_stats() -> None:
    processor = EventProcessor()
    telemetry = make_event("sensor-a", "temperature", 150.0)

    processor.process(telemetry)
    processor.process(telemetry)

    source_stats = processor.stats()["sources"]["sensor-a"]
    assert source_stats["processed"] == 1
    assert source_stats["anomalies"] == 1
    assert source_stats["out_of_order"] == 0
