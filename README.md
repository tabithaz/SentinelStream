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
- Event validation and normalization
- Configurable anomaly detection rules
- Bounded recent-event history with metric and anomaly filtering
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
| POST | `/events` | Validate and process an event |
| GET | `/events/recent` | Read recent events with optional `metric` and `anomalies_only` filters |
| GET | `/events/stats` | Processing statistics |

Recent events are returned newest first. The `limit` query parameter accepts values from 1 to 1000, and the in-memory history is bounded so long-running processes do not accumulate events indefinitely.

## Event Format

```json
{
  "source": "sensor-alpha",
  "metric": "temperature",
  "value": 72.4,
  "timestamp": "2026-09-06T18:00:00Z"
}
```

SentinelStream is being developed incrementally with an emphasis on reliability, testability, and measurable system performance.
