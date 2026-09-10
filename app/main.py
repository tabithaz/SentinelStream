from typing import Annotated

from fastapi import Body, FastAPI, Query

from app.models import TelemetryEvent
from app.processor import EventProcessor

app = FastAPI(title="SentinelStream", version="0.6.0")
processor = EventProcessor()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "sentinelstream"}


@app.post("/events")
def process_event(event: TelemetryEvent) -> dict:
    return processor.process(event)


@app.post("/events/batch")
def process_event_batch(
    events: Annotated[
        list[TelemetryEvent],
        Body(min_length=1, max_length=1000),
    ],
) -> dict:
    return processor.process_many(events)


@app.get("/events/recent")
def recent_events(
    limit: int = Query(default=100, ge=1, le=1000),
    metric: str | None = None,
    source: str | None = None,
    anomalies_only: bool = False,
) -> list[dict]:
    return processor.recent_events(
        limit=limit,
        metric=metric,
        source=source,
        anomalies_only=anomalies_only,
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


@app.get("/events/stats")
def event_stats() -> dict:
    return processor.stats()
