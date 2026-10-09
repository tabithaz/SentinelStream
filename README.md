# SentinelStream

SentinelStream is a FastAPI service for validating telemetry events and diagnosing the health of event-processing streams. It accepts individual events or bounded batches, detects anomalies, duplicates, and ordering problems, and exposes operational reports for throughput, capacity, reliability, and recovery.

The project focuses on the processing and observability layer that would sit behind a Kafka or similar event broker. Its current implementation is self-contained: event history and deduplication keys are bounded in memory so it can be run and reviewed without external infrastructure. Source and metric aggregates are retained for the process lifetime.

## Current capabilities

- Validated single-event and batch ingestion
- Bounded producer idempotency keys for safe single and batch retries
- Optional constant-time API-key authentication for event ingestion
- Optional bounded per-client ingestion rate limiting with retry guidance
- Optional concurrent-ingestion bulkhead with fail-fast overload signaling
- Configurable request-body limits for ingestion resource protection
- Rejection of non-finite readings and blank stream identifiers before state mutation
- UTC timestamp normalization and out-of-order detection
- Configurable metric thresholds and anomaly classification
- Versioned runtime threshold updates with optimistic concurrency control
- Bounded threshold-change audit history with reasons and metric-level diffs
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
- Spreadsheet-safe CSV event export for analyst handoff and incident review
- Bounded, atomic NDJSON replay for incident reproduction
- Source and metric health rankings
- Throughput, burst, capacity, backlog, and partition-skew diagnostics
- Reliability, retry, checkpoint, replay, dead-letter, and recovery analysis modules
- Recent-window reliability SLOs with explicit error-budget burn and exhaustion status
- ETag revalidation for operational summaries and efficient dashboard polling
- Thread-safe batch processing with concurrency regression tests
- FastAPI request validation and interactive OpenAPI documentation
- Prometheus-compatible processing counters and health ratios
- Prometheus RED metrics for HTTP request rate, errors, latency, and in-flight work
- Fail-closed Kubernetes readiness checks with bounded-cardinality headroom
- Highly available Kubernetes deployment with hardened pod security and zero-downtime rollouts
- Failure-domain-aware Kubernetes placement across zones and hosts
- Readiness-aware graceful pod draining during shutdown and rolling updates
- CPU- and memory-aware Kubernetes autoscaling with scale-down stabilization
- Request IDs and structured access logs for cross-service tracing
- Live browser dashboard for event submission and stream-health monitoring
- Non-root Docker image with an application health check
- Automated unit, API, concurrency, and container smoke tests

## Stack

- Python 3.12
- FastAPI and Pydantic
- pytest and HTTPX
- Docker
- Kubernetes
- GitHub Actions

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The dashboard is available at `http://127.0.0.1:8000/dashboard`. It can submit correlated telemetry, display correlation IDs in recent events, inspect incident health across sources and metrics, and monitor a configurable reliability SLO with live error-budget burn. The API is available at `http://127.0.0.1:8000`, with interactive documentation at `http://127.0.0.1:8000/docs`.

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

Set `SENTINELSTREAM_MAX_CONCURRENT_INGESTION` to a positive integer to cap
simultaneous event-writing requests. Saturated callers receive HTTP 503 with
`Retry-After` and `X-Concurrency-Limit` headers instead of waiting and consuming
more application capacity. Slots are released after both successful and failed
requests. The bulkhead is disabled by default. Prometheus reports its configured
capacity, current utilization, and cumulative saturation rejections so operators
can alert before sustained overload affects ingestion availability.

Event-writing request bodies are capped at 1 MiB by default, before JSON or
NDJSON parsing. Set `SENTINELSTREAM_MAX_INGESTION_BYTES` to a positive byte
limit when a deployment needs a different ceiling. Oversized requests receive
HTTP 413 and `X-Max-Request-Bytes`; rejected payloads cannot mutate stream state.
The replay endpoint keeps its existing 1 MiB ceiling when the general limit is raised.

Production memory bounds are configurable without rebuilding the service. Set
`SENTINELSTREAM_HISTORY_SIZE`, `SENTINELSTREAM_DEDUPLICATION_SIZE`,
`SENTINELSTREAM_IDEMPOTENCY_SIZE`, `SENTINELSTREAM_SOURCE_CARDINALITY_LIMIT`,
`SENTINELSTREAM_STREAM_CARDINALITY_LIMIT`, or
`SENTINELSTREAM_THRESHOLD_HISTORY_SIZE` to positive integers. SentinelStream
fails fast during startup when any capacity setting is invalid instead of
silently running with an unintended memory or observability limit.

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

The Prometheus endpoint includes bounded HTTP RED metrics labeled by FastAPI
route templates rather than raw URLs. This exposes request totals by status,
cumulative latency histograms, duration totals, and in-flight work without
creating unbounded labels from event IDs or correlation IDs.

Operational summary endpoints (`/events/stats`, `/events/health-summary`,
`/events/quality-summary`, `/events/reliability`, and `/events/slo`) return
stable ETags with `Cache-Control: no-cache`. Polling clients can send
`If-None-Match` and receive HTTP 304 when the summary has not changed, avoiding
repeated response bodies while still revalidating every request.

## Run on Kubernetes

The deployment manifest starts with two replicas behind a ClusterIP service and
uses separate startup, liveness, and readiness probes. It also sets CPU and
memory budgets, drops Linux capabilities, uses a read-only root filesystem, and
keeps one replica available during voluntary disruptions and rolling updates.
Topology spread constraints direct replicas across availability zones and nodes
while allowing development and single-zone clusters to schedule available capacity.
An `autoscaling/v2` HPA scales the deployment from 2 to 10 replicas at 70% CPU
or 75% memory utilization. Scale-up can react within a minute, while a five-minute
scale-down stabilization window prevents short traffic dips from causing churn.
Before a pod terminates, its pre-stop hook creates a drain marker and waits ten
seconds. The readiness endpoint immediately returns HTTP 503, allowing Kubernetes
to remove the pod from Service endpoints before the process exits while the
remaining termination grace period lets in-flight requests finish.

```bash
kubectl apply -f deploy/kubernetes.yaml
kubectl rollout status deployment/sentinelstream
kubectl port-forward service/sentinelstream 8000:80
```

The autoscaler requires Kubernetes Metrics Server or another implementation of
the resource metrics API. The manifest references
`ghcr.io/tabithaz/sentinelstream:latest`; replace that
image with an immutable release tag from the target registry before a production
rollout. The readiness threshold and ingestion body limit are configured as
environment variables in the manifest.

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
| `GET` | `/ready` | Deployment readiness and cardinality-capacity checks |
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
| `GET` | `/events/export.csv` | Export filtered recent history as spreadsheet-safe CSV |
| `GET` | `/events/stats` | Inspect processing, anomaly, duplicate, and ordering totals |
| `GET` | `/events/sources` | Rank source health |
| `GET` | `/events/metrics` | Rank metric health |
| `GET` | `/events/thresholds` | Read active anomaly thresholds and version |
| `GET` | `/events/thresholds/history` | Audit threshold versions, reasons, and changed metrics |
| `PUT` | `/events/thresholds` | Atomically replace thresholds using `If-Match` |
| `GET` | `/events/throughput` | Analyze recent throughput windows |
| `GET` | `/events/bursts` | Detect bursty arrival windows |
| `GET` | `/events/backpressure` | Model queue capacity and overload |
| `GET` | `/events/health-summary` | Summarize monitored source health |
| `GET` | `/events/quality-summary` | Classify accepted, duplicate, and anomalous data |
| `GET` | `/events/reliability` | Combine stream failure signals |
| `GET` | `/events/slo` | Measure recent reliability and error-budget burn against an SLO |
| `GET` | `/events/recovery` | Recommend recovery action |

Query parameters are validated by FastAPI. Recent-history and batch sizes are bounded to keep request work and process memory predictable.

Use `/events/slo?target_percent=99.9&window_events=1000` to evaluate the most
recent retained events against a reliability target. Anomalous or out-of-order
events consume the budget; the response reports observed reliability, allowed
and remaining bad events, burn percentage, and a `healthy`, `at_risk`, or
`exhausted` deployment signal. A `no_data` result keeps empty windows distinct
from perfect reliability.
Event values must be finite JSON numbers. Source and metric identifiers are trimmed,
limited to 100 characters, and rejected when blank; an invalid batch is rejected
before any event in that request changes processor state.

Anomaly thresholds can be updated without restarting the service. Read the
current configuration and its `ETag`, then send that value in `If-Match` when
replacing the complete threshold set. A concurrent update returns HTTP 412
instead of silently overwriting newer policy. When API-key protection is
configured, threshold writes require the same `X-API-Key` used for ingestion.
Add `X-Change-Reason` to record why a threshold set changed. The bounded audit
history stores each version's timestamp, exact configuration, and added,
removed, or modified metric names; stale and rejected updates are not recorded.

```bash
etag=$(curl -sD - http://127.0.0.1:8000/events/thresholds -o /dev/null \
  | awk 'tolower($1) == "etag:" {print $2}' | tr -d '\r')
curl -X PUT http://127.0.0.1:8000/events/thresholds \
  -H "Content-Type: application/json" -H "If-Match: $etag" \
  -d '{"thresholds":{"temperature":{"minimum":-50,"maximum":100}}}'
```

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

Export up to 1,000 retained events directly to a spreadsheet while preserving
the same source, metric, correlation, anomaly, and time-window filters used by
the NDJSON export:

```bash
curl -OJ "http://127.0.0.1:8000/events/export.csv?source=sensor-alpha&anomalies_only=true"
```

The file is ordered newest-first, includes the event and correlation IDs needed
for investigation, and neutralizes formula-like text before it reaches Excel or
Google Sheets.

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

`GET /health` is the liveness probe and remains healthy while the process can
serve requests. `GET /ready` is the traffic-readiness probe: it returns HTTP 503
before tracked source or stream cardinality reaches its configured bound, so an
orchestrator can drain the instance while monitoring still has headroom. Set
`SENTINELSTREAM_READINESS_CARDINALITY_PERCENT` to a value above 0 and at most
100 to change the default 90% threshold.

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
