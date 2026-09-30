# SentinelStream

SentinelStream is a FastAPI service for validating telemetry events and diagnosing the health of event-processing streams. It accepts individual events or bounded batches, detects anomalies, duplicates, and ordering problems, and exposes operational reports for throughput, capacity, reliability, and recovery.

The project focuses on the processing and observability layer that would sit behind a Kafka or similar event broker. Its current implementation is self-contained: event history and deduplication keys are bounded in memory so it can be run and reviewed without external infrastructure. Source and metric aggregates are retained for the process lifetime.

## Current capabilities

- Validated single-event and batch ingestion
- Bounded producer idempotency keys for safe single and batch retries
- Optional constant-time API-key authentication for event ingestion
- Optional bounded per-client ingestion rate limiting with retry guidance
- Rejection of non-finite readings and blank stream identifiers before state mutation
- UTC timestamp normalization and out-of-order detection
- Configurable metric thresholds and anomaly classification
- Bounded event history and duplicate-delivery suppression
- Deterministic event IDs for tracing accepted events and duplicate deliveries
- End-to-end correlation IDs for distributed incident tracing
- Correlated incident summaries across sources, metrics, anomalies, and ordering faults
- Correlated fault-origin and cross-stream propagation analysis
- Direct event lookup by ID within the bounded retention window
- Bounded event-context windows for incident investigation
- Cursor-based pagination through retained event history
- Bounded source aggregates and LRU stream-ordering state for cardinality safety
- Filtered NDJSON event export for incident analysis and replay pipelines
- Bounded, atomic NDJSON replay for incident reproduction
- Source and metric health rankings
- Throughput, burst, capacity, backlog, and partition-skew diagnostics
- Reliability, retry, checkpoint, replay, dead-letter, and recovery analysis modules
- Thread-safe batch processing with concurrency regression tests
- FastAPI request validation and interactive OpenAPI documentation
- Prometheus-compatible processing counters and health ratios
- Request IDs and structured access logs for cross-service tracing
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

The dashboard is available at `http://127.0.0.1:8000/dashboard`. It can submit correlated telemetry, display correlation IDs in recent events, and inspect incident health across sources and metrics. The API is available at `http://127.0.0.1:8000`, with interactive documentation at `http://127.0.0.1:8000/docs`.

Set `SENTINELSTREAM_API_KEY` to protect every event-writing endpoint. Clients
must then send the configured secret in the `X-API-Key` header. Key comparison
uses constant-time verification, rejected requests cannot mutate stream state,
and read-only analytics, health, metrics, documentation, and the dashboard
remain available. The dashboard's optional API-key field sends the header for
interactive ingestion without storing the secret.

```bash
export SENTINELSTREAM_API_KEY="replace-with-a-secret"
curl -X POST http://127.0.0.1:8000/events \
  -H "X-API-Key: $SENTINELSTREAM_API_KEY" \
  -H "Content-Type: application/json" \
  --data @event.json
```

Set `SENTINELSTREAM_INGEST_RATE_LIMIT` to a positive integer to cap event-writing
requests per client or API key in a rolling 60-second window. Exceeded clients
receive HTTP 429 with `Retry-After`, `X-RateLimit-Limit`, and
`X-RateLimit-Remaining` headers. Client tracking is bounded to 10,000 identities
to prevent the protection layer from introducing unbounded memory growth. The
limit is disabled by default.

```bash
docker run --rm -p 8000:8000 \
  -e SENTINELSTREAM_INGEST_RATE_LIMIT=120 sentinelstream-api
```

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
    "correlation_id": "incident-2026-09-22-001",
    "value": 72.4,
    "timestamp": "2026-09-22T18:00:00Z"
  }'
```

Example response:

```json
{
  "event_id": "16669d45081d7a7a4907b54a8c1fbc60872385426f3e6991fa462824b255566a",
  "accepted": true,
  "duplicate": false,
  "anomaly": false,
  "out_of_order": false,
  "source": "sensor-alpha",
  "metric": "temperature",
  "correlation_id": "incident-2026-09-22-001",
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

Both ingestion endpoints accept an `Idempotency-Key` header. Retrying the same
payload with the same key returns the original result with
`Idempotency-Replayed: true` without incrementing duplicate counters or
processing state again. Reusing a key for a different payload returns HTTP 409.
The least-recently-used key window is capped at 5,000 entries and exposed in
the cardinality section of `/events/stats`.

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service readiness |
| `GET` | `/dashboard` | Live event-processing and reliability dashboard |
| `GET` | `/metrics` | Prometheus-compatible operational metrics |
| `POST` | `/events` | Process one telemetry event |
| `POST` | `/events/batch` | Process 1 to 1000 events atomically |
| `POST` | `/events/replay` | Validate and replay up to 1,000 NDJSON events atomically |
| `GET` | `/events/recent` | Query bounded recent history |
| `GET` | `/events/page` | Traverse retained history with a stable event-ID cursor |
| `GET` | `/events/id/{event_id}` | Retrieve one retained event by its deterministic ID |
| `GET` | `/events/id/{event_id}/context` | Inspect events around one retained event |
| `GET` | `/events/correlations/{correlation_id}` | Summarize one correlated incident or workflow |
| `GET` | `/events/correlations/{correlation_id}/analysis` | Trace the first fault and its propagation across streams |
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

Every accepted or duplicate event response includes a deterministic SHA-256 event ID
derived from its normalized source, metric, value, and UTC timestamp. The same event
keeps the same ID across ingestion, export, and replay, which makes duplicate deliveries
traceable without relying on process-local sequence numbers.

Events may also include an optional `correlation_id` of up to 100 characters.
It is normalized, included in deterministic identity and idempotency checks, and
preserved through history, pagination, NDJSON export, and replay. Use the
`correlation_id` query parameter on `/events/recent`, `/events/page`, or
`/events/export` to follow one incident or distributed workflow across streams.

Summarize the retained portion of a correlated incident without exporting and
aggregating its events manually:

```bash
curl http://127.0.0.1:8000/events/correlations/incident-2026-09-22-001
```

The response reports overall health, event and anomaly counts, ordering faults,
affected sources and metrics, the first and last timestamps, and incident
duration. Unknown correlations return HTTP 404.

For root-cause triage, append `/analysis` to reconstruct faults in retained
processing order. The response identifies the first observed anomaly or
ordering failure, provides a fault-only timeline, and ranks affected streams by
the sequence in which they first degraded. Per-stream event, anomaly, and
ordering-fault counts make propagation visible without exporting and joining
the incident manually.

Retrieve an accepted event directly while it remains in bounded history:

```bash
curl http://127.0.0.1:8000/events/id/16669d45081d7a7a4907b54a8c1fbc60872385426f3e6991fa462824b255566a
```

Malformed IDs return HTTP 422 and valid IDs outside the retained history return HTTP 404.

Investigate the events surrounding a retained event with a chronological context window:

```bash
curl "http://127.0.0.1:8000/events/id/16669d45081d7a7a4907b54a8c1fbc60872385426f3e6991fa462824b255566a/context?before=10&after=10&same_stream=true"
```

The `before` and `after` windows are independently bounded to 100 events. Set
`same_stream=true` to include only events with the target's source and metric.
`has_more_before` and `has_more_after` indicate when additional matching history
exists outside the requested window.

For incremental incident tooling, `GET /events/page?limit=100` returns events
newest-first with `has_more` and a stable `next_cursor`. Pass that cursor into
the next request; source, metric, and anomaly filters remain available. A cursor
that has rolled out of bounded history returns HTTP 404 instead of silently
skipping data.

Per-source health aggregates retain up to 1,000 source identities. Events from
additional identities are counted in a bounded overflow aggregate instead of
growing memory without a bound. Timestamp state used for ordering detection is
maintained as a 5,000-stream LRU window. The stats response exposes both limits,
current usage, and overflow event, anomaly, and ordering counts.

Export up to 1,000 recent records for incident analysis or replay tooling. The
same metric, source, and anomaly filters available for recent history are
supported, along with inclusive ISO 8601 `since` and `until` timestamps. Each
response includes an `X-Event-Count` header:

```bash
curl -OJ "http://127.0.0.1:8000/events/export?source=sensor-alpha&anomalies_only=true"

curl -OJ "http://127.0.0.1:8000/events/export?since=2026-09-25T14:00:00Z&until=2026-09-25T15:00:00Z"
```

The response uses newline-delimited JSON so records can be processed as a
stream without loading the entire export into memory.

Replay an exported incident directly into a clean or restored instance:

```bash
curl -X POST http://127.0.0.1:8000/events/replay \
  -H "Content-Type: application/x-ndjson" \
  --data-binary @sentinelstream-events.ndjson
```

Replay uploads are limited to 1 MiB and 1,000 events. Every line is parsed and
validated before processing begins, so malformed input cannot partially mutate
stream state. Valid events are replayed in timestamp order because exports are
newest-first.

The `/metrics` endpoint uses Prometheus text exposition format and reports received, accepted, duplicate, anomalous, and out-of-order event totals along with anomaly ratios and monitored-source counts. The endpoint intentionally avoids source labels so untrusted source names cannot create unbounded metric cardinality.

Every response includes an `X-Request-ID` header. Callers can provide a safe
request ID using the same header, or SentinelStream generates one. Each request
also writes a compact JSON access log containing the request ID, HTTP method,
path, status code, and duration in milliseconds.

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
- Add sustained load and multi-process deployment tests
