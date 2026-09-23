from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.main as main
from app.models import TelemetryEvent
from app.processor import EventProcessor
from app.prometheus import render_prometheus_metrics


def event(value: float, timestamp: datetime | None = None) -> TelemetryEvent:
    return TelemetryEvent(
        source="sensor-alpha",
        metric="temperature",
        value=value,
        timestamp=timestamp or datetime(2026, 9, 23, 14, 0, tzinfo=timezone.utc),
    )


def test_prometheus_renderer_exposes_empty_processor_metrics() -> None:
    output = render_prometheus_metrics(EventProcessor().stats())

    assert "# TYPE sentinelstream_events_received_total counter" in output
    assert "sentinelstream_events_received_total 0" in output
    assert "sentinelstream_event_anomaly_ratio 0" in output
    assert "sentinelstream_sources_monitored 0" in output
    assert output.endswith("\n")


def test_metrics_endpoint_reports_live_processor_counters(monkeypatch) -> None:
    processor = EventProcessor()
    processor.process(event(72.4))
    processor.process(event(145.0, datetime(2026, 9, 23, 14, 1, tzinfo=timezone.utc)))
    processor.process(event(72.4))
    monkeypatch.setattr(main, "processor", processor)

    response = TestClient(main.app).get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert "sentinelstream_events_received_total 3" in response.text
    assert "sentinelstream_events_processed_total 2" in response.text
    assert "sentinelstream_events_duplicate_total 1" in response.text
    assert "sentinelstream_events_anomaly_total 1" in response.text
    assert "sentinelstream_event_anomaly_ratio 0.5" in response.text
    assert "sentinelstream_sources_monitored 1" in response.text
    assert "sentinelstream_metrics_monitored 1" in response.text
