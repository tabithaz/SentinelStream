# SentinelStream

SentinelStream is a real-time event processing platform for ingesting, validating, analyzing, and monitoring high-volume system telemetry.

The project is designed around production-oriented distributed systems concepts: asynchronous event ingestion, durable message processing, anomaly detection, persistence, observability, and fault-tolerant consumers.

## Architecture

```text
Event Producers
      |
      v
 Apache Kafka
      |
      v
Processing Service
   |        |
   v        v
PostgreSQL  Metrics
   |        |
   v        v
REST API  Prometheus
   |
   v
Live Dashboard
```

## Current Features

- Structured telemetry event model
- Single-event and bounded batch ingestion
- Event validation and normalization
- Configurable anomaly detection rules
- Bounded duplicate-event suppression for replay protection
- Bounded recent-event history with metric and anomaly filtering
- Live throughput and backpressure capacity analysis
- Kafka producer and consumer foundation
- PostgreSQL-ready persistence layer
- Health and event API endpoints
- Docker-based local development environment
- Automated unit tests and CI workflow

## Planned Development

- Dead-letter queue and retry handling
- WebSocket live event streaming
- Redis-backed caching
- Prometheus metrics and Grafana dashboards
- Load and throughput testing
- Kubernetes deployment manifests
- Multi-service horizontal scaling

## Tech Stack

- Python
- FastAPI
- Apache Kafka
- PostgreSQL
- Docker / Docker Compose
- Pytest
- GitHub Actions

## Quick Start

### Local API

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://localhost:8000/health` to verify the service is running.

### Docker

```bash
docker compose up --build
```

## API

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | `/health` | Service health check |
| POST | `/events` | Validate and process one event |
| POST | `/events/batch` | Validate and process 1–1000 events in one request |
| GET | `/events/recent` | Read recent events with optional `metric`, `source`, and `anomalies_only` filters |
| GET | `/events/throughput` | Summarize recent accepted-event throughput across time windows |
| GET | `/events/backpressure` | Model queue growth against a configurable service and queue capacity |
| GET | `/events/sources` | Rank telemetry sources by anomaly rate and health |
| GET | `/events/metrics` | Rank metrics by anomaly rate and health |
| GET | `/events/stats` | Processing statistics, including duplicate-event count |

Batch ingestion returns per-event results plus request-level `received`, `accepted`, `duplicates`, and `anomalies` counts. The processor holds its re-entrant lock across each batch so events from another request cannot interleave with the batch's state updates.

Recent events are returned newest first. The `limit` query parameter accepts values from 1 to 1000, and the in-memory history is bounded so long-running processes do not accumulate events indefinitely.

`/events/backpressure` uses the retained accepted-event history to bin arrivals into event-time windows, simulate draining at `service_capacity_per_window`, and report queue utilization, drain ratio, overloaded windows, and a health status. The endpoint can be scoped to one telemetry source and accepts configurable `window_seconds`, `windows`, and `queue_capacity` values.

The processor also keeps a bounded fingerprint window for accepted events. An exact replay with the same source, metric, value, and timestamp is rejected as a duplicate and does not inflate processed-event, anomaly, or recent-history counts. Duplicate attempts are tracked separately in `/events/stats`.

## Event Format

```json
{
  "source": "sensor-alpha",
  "metric": "temperature",
  "value": 72.4,
  "timestamp": "2026-09-06T18:00:00Z"
}
```

For `/events/batch`, send an array of event objects in this format. Batches are limited to 1000 events to bound request work and memory use.

SentinelStream is being developed incrementally with an emphasis on reliability, testability, and measurable system performance.
