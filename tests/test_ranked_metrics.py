from datetime import datetime, timezone

from app.models import TelemetryEvent
from app.processor import EventProcessor


def event(metric: str, value: float, second: int) -> TelemetryEvent:
    return TelemetryEvent(
        source="vehicle-a",
        metric=metric,
        value=value,
        timestamp=datetime(2026, 9, 9, 18, 0, second, tzinfo=timezone.utc),
    )


def test_ranked_metrics_orders_by_anomaly_rate() -> None:
    processor = EventProcessor()
    processor.process(event("temperature", 150.0, 1))
    processor.process(event("temperature", 80.0, 2))
    processor.process(event("pressure", 300.0, 3))

    ranked = processor.ranked_metrics()

    assert [item["metric"] for item in ranked] == ["pressure", "temperature"]
    assert ranked[0]["anomaly_rate"] == 1.0
    assert ranked[1]["anomaly_rate"] == 0.5
    assert ranked[0]["health"] == "critical"


def test_ranked_metrics_applies_limit_and_health_thresholds() -> None:
    processor = EventProcessor()
    for second, value in enumerate([80.0, 80.0, 80.0, 80.0, 150.0], start=1):
        processor.process(event("temperature", value, second))
    processor.process(event("pressure", 100.0, 10))

    ranked = processor.ranked_metrics(limit=1)

    assert len(ranked) == 1
    assert ranked[0]["metric"] == "temperature"
    assert ranked[0]["anomaly_rate"] == 0.2
    assert ranked[0]["health"] == "watch"


def test_ranked_metrics_rejects_invalid_limit() -> None:
    processor = EventProcessor()

    try:
        processor.ranked_metrics(limit=0)
    except ValueError as exc:
        assert str(exc) == "limit must be greater than zero"
    else:
        raise AssertionError("expected ValueError")
