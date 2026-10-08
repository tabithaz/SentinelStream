import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import hmac
from io import StringIO
import json
import logging
import math
import os
from pathlib import Path
import re
import time
from typing import Annotated
from uuid import uuid4

from fastapi import (
    Body,
    FastAPI,
    Header,
    HTTPException,
    Path as PathParameter,
    Query,
    Request,
    Response,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError

from app.bursts import analyze_event_bursts
from app.bulkhead import InFlightLimiter
from app.capacity import summarize_backpressure
from app.models import TelemetryEvent, ThresholdConfiguration
from app.processor import (
    EventProcessor,
    IdempotencyConflictError,
    ThresholdVersionConflictError,
)
from app.prometheus import RequestMetrics, render_prometheus_metrics
from app.rate_limit import SlidingWindowRateLimiter
from app.recovery import recommend_recovery
from app.reliability import classify_stream_reliability
from app.slo import summarize_event_slo

app = FastAPI(title="SentinelStream", version="1.4.0")
processor = EventProcessor()
request_metrics = RequestMetrics()
DASHBOARD_PATH = Path(__file__).parent / "static" / "dashboard.html"
LOGGER = logging.getLogger("sentinelstream.access")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
MAX_REPLAY_BYTES = 1024 * 1024
MAX_REPLAY_EVENTS = 1000
DEFAULT_MAX_INGESTION_BYTES = 1024 * 1024
DEFAULT_READINESS_CARDINALITY_PERCENT = 90.0
ingestion_rate_limiter = SlidingWindowRateLimiter()
ingestion_concurrency_limiter = InFlightLimiter()


def _ingestion_rate_limit() -> int:
    configured = os.getenv("SENTINELSTREAM_INGEST_RATE_LIMIT", "0")
    try:
        limit = int(configured)
    except ValueError:
        return 0
    return max(0, limit)


def _max_ingestion_bytes() -> int:
    configured = os.getenv(
        "SENTINELSTREAM_MAX_INGESTION_BYTES",
        str(DEFAULT_MAX_INGESTION_BYTES),
    )
    try:
        maximum = int(configured)
    except ValueError:
        return DEFAULT_MAX_INGESTION_BYTES
    return maximum if maximum > 0 else DEFAULT_MAX_INGESTION_BYTES


def _max_concurrent_ingestion() -> int:
    configured = os.getenv("SENTINELSTREAM_MAX_CONCURRENT_INGESTION", "0")
    try:
        limit = int(configured)
    except ValueError:
        return 0
    return max(0, limit)


def _readiness_cardinality_percent() -> float:
    configured = os.getenv(
        "SENTINELSTREAM_READINESS_CARDINALITY_PERCENT",
        str(DEFAULT_READINESS_CARDINALITY_PERCENT),
    )
    try:
        threshold = float(configured)
    except ValueError:
        return DEFAULT_READINESS_CARDINALITY_PERCENT
    if not math.isfinite(threshold) or threshold <= 0 or threshold > 100:
        return DEFAULT_READINESS_CARDINALITY_PERCENT
    return threshold


def _rate_limit_identity(request: Request) -> str:
    api_key = request.headers.get("X-API-Key")
    if api_key:
        digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        return f"api-key:{digest}"
    host = request.client.host if request.client is not None else "unknown"
    return f"client:{host}"


@app.middleware("http")
async def protect_event_writes(request: Request, call_next):
    """Require an API key for event mutation when one is configured."""
    expected_key = os.getenv("SENTINELSTREAM_API_KEY", "")
    is_event_write = request.method in {"POST", "PUT", "PATCH", "DELETE"}
    if expected_key and is_event_write and request.url.path.startswith("/events"):
        supplied_key = request.headers.get("X-API-Key", "")
        if not supplied_key or not hmac.compare_digest(supplied_key, expected_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "valid X-API-Key required"},
                headers={"WWW-Authenticate": "ApiKey"},
            )
    return await call_next(request)


@app.middleware("http")
async def limit_event_ingestion(request: Request, call_next):
    """Apply an optional per-client sliding-window limit to event writes."""
    limit = _ingestion_rate_limit()
    is_event_write = request.method == "POST" and request.url.path.startswith("/events")
    if not limit or not is_event_write:
        return await call_next(request)

    decision = ingestion_rate_limiter.check(
        _rate_limit_identity(request),
        limit,
        time.monotonic(),
    )
    headers = {
        "X-RateLimit-Limit": str(limit),
        "X-RateLimit-Remaining": str(decision.remaining),
    }
    if not decision.allowed:
        headers["Retry-After"] = str(decision.retry_after_seconds)
        return JSONResponse(
            status_code=429,
            content={"detail": "event ingestion rate limit exceeded"},
            headers=headers,
        )

    response = await call_next(request)
    response.headers.update(headers)
    return response


@app.middleware("http")
async def limit_concurrent_ingestion(request: Request, call_next):
    """Fail fast when concurrent event-writing work reaches its configured cap."""
    limit = _max_concurrent_ingestion()
    is_event_write = request.method == "POST" and request.url.path.startswith("/events")
    if not limit or not is_event_write:
        return await call_next(request)

    if not ingestion_concurrency_limiter.try_acquire(limit):
        return JSONResponse(
            status_code=503,
            content={"detail": "event ingestion concurrency limit reached"},
            headers={
                "Retry-After": "1",
                "X-Concurrency-Limit": str(limit),
            },
        )
    try:
        response = await call_next(request)
        response.headers["X-Concurrency-Limit"] = str(limit)
        return response
    finally:
        ingestion_concurrency_limiter.release()


@app.middleware("http")
async def limit_ingestion_payloads(request: Request, call_next):
    """Reject oversized event writes before request parsing or state mutation."""
    is_event_write = request.method == "POST" and request.url.path.startswith("/events")
    if not is_event_write:
        return await call_next(request)

    maximum = _max_ingestion_bytes()
    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            if int(declared_length) > maximum:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "event payload exceeds configured byte limit"},
                    headers={"X-Max-Request-Bytes": str(maximum)},
                )
        except ValueError:
            pass

    body = await request.body()
    if len(body) > maximum:
        return JSONResponse(
            status_code=413,
            content={"detail": "event payload exceeds configured byte limit"},
            headers={"X-Max-Request-Bytes": str(maximum)},
        )
    return await call_next(request)


@app.middleware("http")
async def request_trace(request: Request, call_next):
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        supplied_request_id
        if REQUEST_ID_PATTERN.fullmatch(supplied_request_id)
        else uuid4().hex
    )
    started_at = time.perf_counter()
    request_metrics.begin()
    try:
        response = await call_next(request)
    except BaseException:
        request_metrics.observe(
            request.method,
            "unhandled",
            500,
            time.perf_counter() - started_at,
        )
        raise
    duration_seconds = time.perf_counter() - started_at
    route = request.scope.get("route")
    route_path = getattr(route, "path", "unmatched")
    request_metrics.observe(
        request.method,
        route_path,
        response.status_code,
        duration_seconds,
    )
    duration_ms = round(duration_seconds * 1000, 3)
    response.headers["X-Request-ID"] = request_id
    LOGGER.info(
        json.dumps(
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
            separators=(",", ":"),
        )
    )
    return response


def _utc_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _validate_time_window(since: datetime | None, until: datetime | None) -> None:
    if since is not None and until is not None and since > until:
        raise HTTPException(
            status_code=422,
            detail="since must be earlier than or equal to until",
        )


def _normalize_correlation_filter(correlation_id: str | None) -> str | None:
    if correlation_id is None:
        return None
    normalized = correlation_id.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="correlation_id must not be blank")
    return normalized


def _json_safe(value: object) -> object:
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _spreadsheet_safe(value: object) -> object:
    """Keep exported text from being evaluated as a spreadsheet formula."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


@app.exception_handler(RequestValidationError)
async def validation_error_response(
    _request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": _json_safe(error.errors())})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "sentinelstream"}


@app.get("/ready")
def readiness() -> JSONResponse:
    """Fail closed before bounded cardinality prevents full-fidelity monitoring."""
    cardinality = processor.stats()["cardinality"]
    threshold = _readiness_cardinality_percent()
    checks = {}
    for name, tracked_key, limit_key in (
        ("sources", "tracked_sources", "source_limit"),
        ("streams", "tracked_streams", "stream_limit"),
    ):
        tracked = cardinality[tracked_key]
        limit = cardinality[limit_key]
        utilization = 100.0 * tracked / limit
        checks[name] = {
            "ready": utilization < threshold,
            "tracked": tracked,
            "limit": limit,
            "utilization_percent": round(utilization, 2),
        }

    ready = all(check["ready"] for check in checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "service": "sentinelstream",
            "cardinality_threshold_percent": threshold,
            "checks": checks,
        },
        headers={} if ready else {"Retry-After": "5"},
    )


@app.get("/dashboard", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD_PATH, media_type="text/html")


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    return Response(
        content=render_prometheus_metrics(processor.stats(), request_metrics.snapshot()),
        media_type="text/plain; version=0.0.4",
    )


@app.post("/events")
def process_event(
    event: TelemetryEvent,
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=128,
            pattern=r"^[A-Za-z0-9._:-]+$",
        ),
    ] = None,
) -> Response:
    if idempotency_key is None:
        return JSONResponse(content=processor.process(event))
    try:
        result, replayed = processor.process_idempotent(event, idempotency_key)
    except IdempotencyConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return JSONResponse(
        content=result,
        headers={"Idempotency-Replayed": str(replayed).lower()},
    )


@app.post("/events/batch")
def process_event_batch(
    events: Annotated[
        list[TelemetryEvent],
        Body(min_length=1, max_length=1000),
    ],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=128,
            pattern=r"^[A-Za-z0-9._:-]+$",
        ),
    ] = None,
) -> Response:
    if idempotency_key is None:
        return JSONResponse(content=processor.process_many(events))
    try:
        result, replayed = processor.process_many_idempotent(events, idempotency_key)
    except IdempotencyConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return JSONResponse(
        content=result,
        headers={"Idempotency-Replayed": str(replayed).lower()},
    )


@app.post("/events/replay")
async def replay_events(request: Request) -> dict:
    """Validate and atomically process a bounded NDJSON event export."""
    media_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if media_type != "application/x-ndjson":
        raise HTTPException(
            status_code=415,
            detail="content type must be application/x-ndjson",
        )

    body = await request.body()
    if len(body) > MAX_REPLAY_BYTES:
        raise HTTPException(status_code=413, detail="replay payload exceeds 1 MiB")
    try:
        lines = body.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=422, detail="replay payload must be UTF-8") from error
    if not lines:
        raise HTTPException(status_code=422, detail="replay payload contains no events")
    if len(lines) > MAX_REPLAY_EVENTS:
        raise HTTPException(status_code=413, detail="replay payload exceeds 1000 events")

    events: list[TelemetryEvent] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise HTTPException(
                status_code=422,
                detail=f"replay line {line_number}: blank records are not allowed",
            )
        try:
            record = json.loads(line)
            events.append(TelemetryEvent.model_validate(record))
        except (json.JSONDecodeError, ValidationError) as error:
            raise HTTPException(
                status_code=422,
                detail=f"replay line {line_number}: invalid telemetry event",
            ) from error

    events.sort(key=lambda event: event.timestamp)
    return processor.process_many(events)


@app.get("/events/recent")
def recent_events(
    limit: int = Query(default=100, ge=1, le=1000),
    metric: str | None = None,
    source: str | None = None,
    correlation_id: str | None = Query(default=None, min_length=1, max_length=100),
    anomalies_only: bool = False,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[dict]:
    correlation_id = _normalize_correlation_filter(correlation_id)
    since = _utc_timestamp(since)
    until = _utc_timestamp(until)
    _validate_time_window(since, until)
    return processor.recent_events(
        limit=limit,
        metric=metric,
        source=source,
        correlation_id=correlation_id,
        anomalies_only=anomalies_only,
        since=since,
        until=until,
    )


@app.get("/events/id/{event_id}")
def event_by_id(
    event_id: Annotated[str, PathParameter(pattern=r"^[0-9a-f]{64}$")],
) -> dict:
    event = processor.event_by_id(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found in retained history")
    return event


@app.get("/events/id/{event_id}/context")
def event_context(
    event_id: Annotated[str, PathParameter(pattern=r"^[0-9a-f]{64}$")],
    before: int = Query(default=5, ge=0, le=100),
    after: int = Query(default=5, ge=0, le=100),
    same_stream: bool = False,
) -> dict:
    context = processor.event_context(
        event_id,
        before=before,
        after=after,
        same_stream=same_stream,
    )
    if context is None:
        raise HTTPException(status_code=404, detail="event not found in retained history")
    return context


@app.get("/events/correlations/{correlation_id}")
def correlation_summary(
    correlation_id: Annotated[
        str,
        PathParameter(min_length=1, max_length=100),
    ],
) -> dict:
    normalized = _normalize_correlation_filter(correlation_id)
    summary = processor.correlation_summary(normalized)
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail="correlation not found in retained history",
        )
    return summary


@app.get("/events/correlations/{correlation_id}/analysis")
def correlation_fault_analysis(
    correlation_id: Annotated[
        str,
        PathParameter(min_length=1, max_length=100),
    ],
) -> dict:
    normalized = _normalize_correlation_filter(correlation_id)
    analysis = processor.correlation_fault_analysis(normalized)
    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="correlation not found in retained history",
        )
    return analysis


@app.get("/events/page")
def paginated_events(
    limit: int = Query(default=100, ge=1, le=1000),
    cursor: str | None = Query(default=None, pattern=r"^[0-9a-f]{64}$"),
    metric: str | None = None,
    source: str | None = None,
    correlation_id: str | None = Query(default=None, min_length=1, max_length=100),
    anomalies_only: bool = False,
) -> dict:
    correlation_id = _normalize_correlation_filter(correlation_id)
    try:
        return processor.event_page(
            limit=limit,
            cursor=cursor,
            metric=metric,
            source=source,
            correlation_id=correlation_id,
            anomalies_only=anomalies_only,
        )
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail="cursor not found in retained history",
        ) from error


@app.get("/events/export", include_in_schema=True)
def export_events(
    limit: int = Query(default=1000, ge=1, le=1000),
    metric: str | None = None,
    source: str | None = None,
    correlation_id: str | None = Query(default=None, min_length=1, max_length=100),
    anomalies_only: bool = False,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Response:
    """Export bounded recent history as newline-delimited JSON."""
    since = _utc_timestamp(since)
    until = _utc_timestamp(until)
    _validate_time_window(since, until)
    correlation_id = _normalize_correlation_filter(correlation_id)
    events = processor.recent_events(
        limit=limit,
        metric=metric,
        source=source,
        correlation_id=correlation_id,
        anomalies_only=anomalies_only,
        since=since,
        until=until,
    )
    content = "".join(
        json.dumps(event, separators=(",", ":"), allow_nan=False) + "\n"
        for event in events
    )
    return Response(
        content=content,
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": 'attachment; filename="sentinelstream-events.ndjson"',
            "X-Event-Count": str(len(events)),
        },
    )


@app.get("/events/export.csv", include_in_schema=True)
def export_events_csv(
    limit: int = Query(default=1000, ge=1, le=1000),
    metric: str | None = None,
    source: str | None = None,
    correlation_id: str | None = Query(default=None, min_length=1, max_length=100),
    anomalies_only: bool = False,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Response:
    """Export bounded recent history as spreadsheet-safe CSV."""
    since = _utc_timestamp(since)
    until = _utc_timestamp(until)
    _validate_time_window(since, until)
    correlation_id = _normalize_correlation_filter(correlation_id)
    events = processor.recent_events(
        limit=limit,
        metric=metric,
        source=source,
        correlation_id=correlation_id,
        anomalies_only=anomalies_only,
        since=since,
        until=until,
    )
    columns = (
        "event_id",
        "source",
        "metric",
        "correlation_id",
        "value",
        "timestamp",
        "anomaly",
        "out_of_order",
    )
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for event in events:
        writer.writerow(
            {
                column: _spreadsheet_safe(event.get(column, ""))
                for column in columns
            }
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="sentinelstream-events.csv"',
            "X-Event-Count": str(len(events)),
        },
    )


@app.get("/events/throughput")
def throughput_summary(
    window_seconds: int = Query(default=60, ge=1, le=3600),
    windows: int = Query(default=5, ge=1, le=120),
    target_per_window: int = Query(default=100, ge=1),
    source: str | None = None,
) -> dict:
    return processor.throughput_summary(
        window_seconds=window_seconds,
        windows=windows,
        target_per_window=target_per_window,
        source=source,
    )


@app.get("/events/bursts")
def burst_summary(
    window_seconds: int = Query(default=60, ge=1, le=3600),
    windows: int = Query(default=5, ge=1, le=120),
    multiplier: float = Query(default=2.0, gt=1.0, le=100.0),
    source: str | None = None,
) -> dict:
    windowed = processor.throughput_summary(
        window_seconds=window_seconds,
        windows=windows,
        target_per_window=1,
        source=source,
    )
    analysis = analyze_event_bursts(windowed["window_counts"], multiplier=multiplier)
    return {
        **asdict(analysis),
        "window_seconds": window_seconds,
        "window_counts": windowed["window_counts"],
        "multiplier": multiplier,
        "source": source,
        "anchor_timestamp": windowed["anchor_timestamp"],
    }


@app.get("/events/backpressure")
def backpressure_summary(
    window_seconds: int = Query(default=60, ge=1, le=3600),
    windows: int = Query(default=5, ge=1, le=120),
    service_capacity_per_window: int = Query(default=100, ge=1),
    queue_capacity: int = Query(default=1000, ge=1),
    source: str | None = None,
) -> dict:
    events = processor.recent_events(limit=1000, source=source)
    return summarize_backpressure(
        events,
        window_seconds=window_seconds,
        windows=windows,
        service_capacity_per_window=service_capacity_per_window,
        queue_capacity=queue_capacity,
        source=source,
    )


@app.get("/events/sources")
def ranked_sources(
    limit: int = Query(default=10, ge=1, le=100),
) -> list[dict]:
    return processor.ranked_sources(limit=limit)


@app.get("/events/metrics")
def ranked_metrics(
    limit: int = Query(default=10, ge=1, le=100),
) -> list[dict]:
    return processor.ranked_metrics(limit=limit)


@app.get("/events/thresholds")
def anomaly_thresholds() -> JSONResponse:
    configuration = processor.threshold_configuration()
    return JSONResponse(
        content=configuration,
        headers={"ETag": f'"{configuration["version"]}"'},
    )


@app.get("/events/thresholds/history")
def anomaly_threshold_history(
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    history = processor.threshold_history(limit=limit)
    return {
        "records": history,
        "count": len(history),
        "current_version": processor.threshold_configuration()["version"],
    }


@app.put("/events/thresholds")
def replace_anomaly_thresholds(
    configuration: ThresholdConfiguration,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    change_reason: Annotated[
        str | None,
        Header(alias="X-Change-Reason", min_length=1, max_length=200),
    ] = None,
) -> JSONResponse:
    if if_match is None:
        raise HTTPException(
            status_code=428,
            detail="If-Match with the current threshold version is required",
        )
    match = re.fullmatch(r'"([1-9][0-9]*)"', if_match)
    if match is None:
        raise HTTPException(
            status_code=400,
            detail='If-Match must be a quoted positive threshold version, such as "1"',
        )

    thresholds = {
        metric: (bounds.minimum, bounds.maximum)
        for metric, bounds in configuration.thresholds.items()
    }
    if change_reason is not None and not change_reason.strip():
        raise HTTPException(
            status_code=422,
            detail="X-Change-Reason must not be blank",
        )
    try:
        updated = processor.replace_thresholds(
            thresholds,
            int(match.group(1)),
            reason=change_reason,
        )
    except ThresholdVersionConflictError as error:
        return JSONResponse(
            status_code=412,
            content={"detail": str(error), "current_version": error.current_version},
            headers={"ETag": f'"{error.current_version}"'},
        )
    return JSONResponse(
        content=updated,
        headers={"ETag": f'"{updated["version"]}"'},
    )


@app.get("/events/health-summary")
def health_summary() -> dict:
    sources = processor.ranked_sources(limit=100)
    counts = {"healthy": 0, "watch": 0, "critical": 0}
    for source in sources:
        counts[source["health"]] += 1

    monitored = len(sources)
    degraded = counts["watch"] + counts["critical"]
    return {
        "sources_monitored": monitored,
        "healthy_sources": counts["healthy"],
        "watch_sources": counts["watch"],
        "critical_sources": counts["critical"],
        "degraded_sources": degraded,
        "degraded_share": degraded / monitored if monitored else 0.0,
    }


@app.get("/events/quality-summary")
def quality_summary() -> dict:
    stats = processor.stats()
    received = stats["processed"] + stats["duplicates"]
    duplicate_rate = stats["duplicates"] / received if received else 0.0
    anomaly_rate = stats["anomaly_rate"]

    if duplicate_rate >= 0.25 or anomaly_rate >= 0.5:
        quality = "unreliable"
    elif duplicate_rate >= 0.10 or anomaly_rate >= 0.2:
        quality = "degraded"
    else:
        quality = "healthy"

    return {
        "received": received,
        "accepted": stats["processed"],
        "duplicates": stats["duplicates"],
        "anomalies": stats["anomalies"],
        "acceptance_rate": stats["processed"] / received if received else 0.0,
        "duplicate_rate": duplicate_rate,
        "anomaly_rate": anomaly_rate,
        "quality": quality,
    }


@app.get("/events/reliability")
def stream_reliability() -> dict:
    stats = processor.stats()
    received = stats["processed"] + stats["duplicates"]
    duplicate_rate = stats["duplicates"] / received if received else 0.0
    result = classify_stream_reliability(
        anomaly_rate=stats["anomaly_rate"],
        duplicate_rate=duplicate_rate,
        out_of_order_rate=stats["out_of_order_rate"],
    )
    return {
        **result,
        "anomaly_rate": stats["anomaly_rate"],
        "duplicate_rate": duplicate_rate,
        "out_of_order_rate": stats["out_of_order_rate"],
    }


@app.get("/events/slo")
def event_reliability_slo(
    target_percent: float = Query(default=99.0, gt=0, le=100),
    window_events: int = Query(default=1000, ge=1, le=1000),
) -> dict:
    """Report event reliability and remaining error budget for a recent window."""
    events = processor.recent_events(limit=window_events)
    return summarize_event_slo(
        events,
        target_percent=target_percent,
        window_events=window_events,
    )


@app.get("/events/recovery")
def recovery_summary(
    window_seconds: int = Query(default=60, ge=1, le=3600),
    windows: int = Query(default=5, ge=1, le=120),
    service_capacity_per_window: int = Query(default=100, ge=1),
    queue_capacity: int = Query(default=1000, ge=1),
    source: str | None = None,
) -> dict:
    events = processor.recent_events(limit=1000, source=source)
    stats = processor.stats()

    if source is None:
        anomaly_rate = stats["anomaly_rate"]
        out_of_order_rate = stats["out_of_order_rate"]
    else:
        source_stats = stats["sources"].get(source)
        anomaly_rate = source_stats["anomaly_rate"] if source_stats else 0.0
        out_of_order_rate = source_stats["out_of_order_rate"] if source_stats else 0.0

    consecutive_failures = 0
    for event in events:
        if not (event["anomaly"] or event["out_of_order"]):
            break
        consecutive_failures += 1

    capacity = summarize_backpressure(
        events,
        window_seconds=window_seconds,
        windows=windows,
        service_capacity_per_window=service_capacity_per_window,
        queue_capacity=queue_capacity,
        source=source,
    )
    queue_utilization = min(1.0, capacity["peak_capacity_utilization"] / 100.0)
    error_rate = max(anomaly_rate, out_of_order_rate)
    plan = recommend_recovery(
        error_rate=error_rate,
        queue_utilization=queue_utilization,
        consecutive_failures=consecutive_failures,
    )

    return {
        **asdict(plan),
        "source": source,
        "error_rate": error_rate,
        "anomaly_rate": anomaly_rate,
        "out_of_order_rate": out_of_order_rate,
        "queue_utilization": queue_utilization,
        "consecutive_failures": consecutive_failures,
        "backpressure_status": capacity["status"],
    }


@app.get("/events/stats")
def event_stats() -> dict:
    return processor.stats()
