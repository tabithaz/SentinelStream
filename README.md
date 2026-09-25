# SentinelStream

SentinelStream is a FastAPI service for validating telemetry events and diagnosing the health of event-processing streams. It accepts individual events or bounded batches, detects anomalies, duplicates, and ordering problems, and exposes operational reports for throughput, capacity, reliability, and recovery.

The project focuses on the processing and observability layer that would sit behind a Kafka or similar event broker. Its current implementation is self-contained: event history and deduplication keys are bounded in memory so it can be run and reviewed without external infrastructure. Source and metric aggregates are retained for the process lifetime.

## Current capabilities

- Validated single-event and batch ingestion
- Rejection of non-finite readings and blank stream identifiers before state mutation
- UTC timestamp normalization and out-of-order detection
- Configurable metric thresholds and anomaly classification
- Bounded event history and duplicate-delivery suppression
- Filtered NDJSON event export for incident analysis and replay pipelines
- Source and metric health rankings
- Throughput, burst, capacity, backlog, and partition-skew diagnostics
- Reliability, retry, checkpoint, replay, dead-letter, and recovery analysis modules
- Thread-safe batch processing with concurrency regression tests
- FastAPI request validation and interactive OpenAPI documentation
- Prometheus-compatible processing counters and health ratios
- Live browser dashboard for event submission and stream-health monitoring
- Non-root Docker image with an application health check
- Automated unit, API, concurrency, and container smoke tests

## Stack

- Python 3.12
- FastAPI and Pydantic
- pytest and HTTPX
- Docker
- GitHub Actions

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The dashboard is available at `http://127.0.0.1:8000/dashboard`. The API is available at `http://127.0.0.1:8000`, with interactive documentation at `http://127.0.0.1:8000/docs`.

## Run with Docker

```bash
docker build -t sentinelstream-api .
docker run --rm -p 8000:8000 sentinelstream-api
```

Verify the running service:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/metrics
```

## Runnable example

Process a normal event:

```bash
curl -X POST http://127.0.0.1:8000/events \
  -H "Content-Type: application/json" \
  -d '{
    "source": "sensor-alpha",
    "metric": "temperature",
    "value": 72.4,
    "timestamp": "2026-09-22T18:00:00Z"
  }'
```

Example response:

```json
{
  "accepted": true,
  "duplicate": false,
  "anomaly": false,
  "out_of_order": false,
  "source": "sensor-alpha",
  "metric": "temperature",
  "value": 72.4,
  "timestamp": "2026-09-22T18:00:00+00:00"
}
```

Send a bounded batch and inspect stream health:

```bash
curl -X POST http://127.0.0.1:8000/events/batch \
  -H "Content-Type: application/json" \
  -d '[
    {"source":"sensor-alpha","metric":"temperature","value":72.4,"timestamp":"2026-09-22T18:00:00Z"},
    {"source":"sensor-alpha","metric":"temperature","value":145.0,"timestamp":"2026-09-22T18:01:00Z"}
  ]'

curl http://127.0.0.1:8000/events/reliability
curl http://127.0.0.1:8000/events/recovery
```

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service readiness |
| `GET` | `/dashboard` | Live event-processing and reliability dashboard |
| `GET` | `/metrics` | Prometheus-compatible operational metrics |
| `POST` | `/events` | Process one telemetry event |
| `POST` | `/events/batch` | Process 1 to 1000 events atomically |
| `GET` | `/events/recent` | Query bounded recent history |
| `GET` | `/events/export` | Export filtered recent history as NDJSON |
| `GET` | `/events/stats` | Inspect processing, anomaly, duplicate, and ordering totals |
| `GET` | `/events/sources` | Rank source health |
| `GET` | `/events/metrics` | Rank metric health |
| `GET` | `/events/throughput` | Analyze recent throughput windows |
| `GET` | `/events/bursts` | Detect bursty arrival windows |
| `GET` | `/events/backpressure` | Model queue capacity and overload |
| `GET` | `/events/health-summary` | Summarize monitored source health |
| `GET` | `/events/quality-summary` | Classify accepted, duplicate, and anomalous data |
| `GET` | `/events/reliability` | Combine stream failure signals |
| `GET` | `/events/recovery` | Recommend recovery action |

Query parameters are validated by FastAPI. Recent-history and batch sizes are bounded to keep request work and process memory predictable.
Event values must be finite JSON numbers. Source and metric identifiers are trimmed,
limited to 100 characters, and rejected when blank; an invalid batch is rejected
before any event in that request changes processor state.

Export up to 1,000 recent records for incident analysis or replay tooling. The
same metric, source, and anomaly filters available for recent history are
supported, and each response includes an `X-Event-Count` header:

```bash
curl -OJ "http://127.0.0.1:8000/events/export?source=sensor-alpha&anomalies_only=true"
```

The response uses newline-delimited JSON so records can be processed as a
stream without loading the entire export into memory.

The `/metrics` endpoint uses Prometheus text exposition format and reports received, accepted, duplicate, anomalous, and out-of-order event totals along with anomaly ratios and monitored-source counts. The endpoint intentionally avoids source labels so untrusted source names cannot create unbounded metric cardinality.

## Run tests

```bash
PYTHONPATH=. pytest -q
```

The suite covers the API, processing rules, diagnostic modules, validation failures, event ordering, duplicate delivery, concurrency, and batch behavior.

## Architecture

```text
Telemetry producers
        |
        v
 FastAPI ingestion
        |
        v
Thread-safe processor
   |           |
   v           v
Bounded       Health and
history       recovery reports
```

## v1.0 scope

SentinelStream v1.0 includes validated event ingestion, bounded thread-safe processing, anomaly and replay protection, operational diagnostics, Prometheus metrics, a live dashboard, automated tests, and a containerized runnable demo.

## Future extensions

- Add a broker adapter for Kafka-compatible ingestion
- Persist events and checkpoints outside process memory
- Cap or expire per-source aggregates for untrusted, high-cardinality source IDs
- Add sustained load and multi-process deployment tests
