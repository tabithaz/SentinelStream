from datetime import datetime, timezone

from app.models import TelemetryEvent
from app.processor import EventProcessor


def event(metric: str, value: float) -> TelemetryEvent:
    return TelemetryEvent(
        source="test-sensor",
        metric=metric,
        value=value,
        timestamp=datetime.now(timezone.utc),
    )


def test_normal_event_is_accepted() -> None:
    processor = EventProcessor()
    result = processor.process(event("temperature", 72.0))

    assert result["accepted"] is True
    assert result["anomaly"] is False


def test_out_of_range_event_is_anomaly() -> None:
    processor = EventProcessor()
    result = processor.process(event("temperature", 150.0))

    assert result["anomaly"] is True
    assert processor.stats()["anomalies"] == 1


def test_processor_tracks_event_count() -> None:
    processor = EventProcessor()
    processor.process(event("voltage", 12.0))
    processor.process(event("pressure", 90.0))

    assert processor.stats()["processed"] == 2


def test_stats_include_per_metric_counts_and_rates() -> None:
    processor = EventProcessor()
    processor.process(event("temperature", 72.0))
    processor.process(event("Temperature", 150.0))
    processor.process(event("voltage", 12.0))

    stats = processor.stats()

    assert stats["anomaly_rate"] == 1 / 3
    assert stats["metrics"]["temperature"] == {
        "processed": 2,
        "anomalies": 1,
        "anomaly_rate": 0.5,
    }
    assert stats["metrics"]["voltage"] == {
        "processed": 1,
        "anomalies": 0,
        "anomaly_rate": 0.0,
    }


def test_empty_stats_have_zero_anomaly_rate() -> None:
    processor = EventProcessor()

    stats = processor.stats()

    assert stats["processed"] == 0
    assert stats["anomalies"] == 0
    assert stats["anomaly_rate"] == 0.0
    assert stats["metrics"] == {}
