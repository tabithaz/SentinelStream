from datetime import datetime, timezone

import pytest

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


def test_custom_thresholds_override_defaults() -> None:
    processor = EventProcessor({"temperature": (10.0, 20.0)})

    assert processor.process(event("temperature", 25.0))["anomaly"] is True
    assert processor.process(event("temperature", 15.0))["anomaly"] is False
    assert processor.process(event("voltage", 100.0))["anomaly"] is False


def test_custom_threshold_metric_names_are_case_insensitive() -> None:
    processor = EventProcessor({"Temperature": (0.0, 10.0)})

    assert processor.process(event("TEMPERATURE", 11.0))["anomaly"] is True


def test_invalid_threshold_range_is_rejected() -> None:
    with pytest.raises(ValueError, match="minimum exceeds maximum"):
        EventProcessor({"temperature": (100.0, 0.0)})


def test_recent_events_are_returned_newest_first() -> None:
    processor = EventProcessor()
    processor.process(event("temperature", 70.0))
    processor.process(event("pressure", 90.0))
    processor.process(event("voltage", 12.0))

    recent = processor.recent_events(limit=2)

    assert [item["metric"] for item in recent] == ["voltage", "pressure"]


def test_recent_event_history_is_bounded() -> None:
    processor = EventProcessor(history_size=2)
    processor.process(event("temperature", 70.0))
    processor.process(event("pressure", 90.0))
    processor.process(event("voltage", 12.0))

    recent = processor.recent_events(limit=10)

    assert [item["metric"] for item in recent] == ["voltage", "pressure"]


def test_recent_events_support_metric_and_anomaly_filters() -> None:
    processor = EventProcessor()
    processor.process(event("Temperature", 70.0))
    processor.process(event("temperature", 150.0))
    processor.process(event("pressure", 300.0))

    recent = processor.recent_events(
        limit=10,
        metric="TEMPERATURE",
        anomalies_only=True,
    )

    assert len(recent) == 1
    assert recent[0]["metric"] == "temperature"
    assert recent[0]["anomaly"] is True


def test_invalid_history_size_and_recent_limit_are_rejected() -> None:
    with pytest.raises(ValueError, match="history_size"):
        EventProcessor(history_size=0)

    processor = EventProcessor()
    with pytest.raises(ValueError, match="limit"):
        processor.recent_events(limit=0)
