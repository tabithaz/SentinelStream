from datetime import datetime, timezone

import pytest

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


def test_source_aggregates_are_bounded_with_visible_overflow() -> None:
    processor = EventProcessor(source_cardinality_limit=2)

    processor.process(make_event("sensor-a", "temperature", 70.0))
    processor.process(make_event("sensor-b", "temperature", 150.0))
    processor.process(make_event("sensor-c", "temperature", 150.0))
    processor.process(make_event("sensor-d", "pressure", 90.0))
    processor.process(make_event("sensor-a", "voltage", 12.0))

    stats = processor.stats()

    assert set(stats["sources"]) == {"sensor-a", "sensor-b"}
    assert stats["sources"]["sensor-a"]["processed"] == 2
    assert stats["cardinality"] == {
        "tracked_sources": 2,
        "source_limit": 2,
        "source_overflow_events": 2,
        "source_overflow_anomalies": 1,
        "source_overflow_out_of_order": 0,
        "tracked_streams": 5,
        "stream_limit": 5000,
    }


def test_stream_ordering_state_uses_bounded_lru_window() -> None:
    processor = EventProcessor(stream_cardinality_limit=2)
    base = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)

    processor.process(
        TelemetryEvent(source="sensor-a", metric="temperature", value=70, timestamp=base)
    )
    processor.process(
        TelemetryEvent(source="sensor-b", metric="temperature", value=70, timestamp=base)
    )
    processor.process(
        TelemetryEvent(source="sensor-a", metric="temperature", value=71, timestamp=base)
    )
    processor.process(
        TelemetryEvent(source="sensor-c", metric="temperature", value=70, timestamp=base)
    )
    result = processor.process(
        TelemetryEvent(
            source="sensor-b",
            metric="temperature",
            value=69,
            timestamp=datetime(2026, 9, 26, 11, 59, tzinfo=timezone.utc),
        )
    )

    assert result["out_of_order"] is False
    assert processor.stats()["cardinality"]["tracked_streams"] == 2


def test_invalid_cardinality_limits_are_rejected() -> None:
    with pytest.raises(ValueError, match="source_cardinality_limit"):
        EventProcessor(source_cardinality_limit=0)
    with pytest.raises(ValueError, match="stream_cardinality_limit"):
        EventProcessor(stream_cardinality_limit=0)
