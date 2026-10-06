from datetime import datetime, timezone

from fastapi.testclient import TestClient

import app.main as main
from app.models import TelemetryEvent
from app.processor import EventProcessor
from app.prometheus import RequestMetrics, render_prometheus_metrics


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


def test_request_metrics_exports_bounded_red_metrics(monkeypatch) -> None:
    metrics = RequestMetrics()
    monkeypatch.setattr(main, "request_metrics", metrics)
    client = TestClient(main.app)

    assert client.get("/health").status_code == 200
    assert client.get("/events/recent?limit=0").status_code == 422
    response = client.get("/metrics")

    assert response.status_code == 200
    assert (
        'sentinelstream_http_requests_total{method="GET",route="/health",status="200"} 1'
        in response.text
    )
    assert (
        'sentinelstream_http_requests_total{method="GET",route="/events/recent",status="422"} 1'
        in response.text
    )
    assert (
        'sentinelstream_http_request_duration_seconds_bucket'
        '{method="GET",route="/health",le="+Inf"} 1'
        in response.text
    )
    assert (
        'sentinelstream_http_request_duration_seconds_count'
        '{method="GET",route="/health"} 1'
        in response.text
    )
    assert "sentinelstream_http_requests_in_flight 1" in response.text


def test_request_metrics_uses_route_templates_for_dynamic_paths(monkeypatch) -> None:
    metrics = RequestMetrics()
    monkeypatch.setattr(main, "request_metrics", metrics)
    client = TestClient(main.app)

    response = client.get("/events/id/" + "a" * 64)
    assert response.status_code == 404
    output = client.get("/metrics").text

    assert 'route="/events/id/{event_id}"' in output
    assert "a" * 64 not in output
