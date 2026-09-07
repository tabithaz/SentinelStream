from fastapi import FastAPI, Query

from app.models import TelemetryEvent
from app.processor import EventProcessor

app = FastAPI(title="SentinelStream", version="0.1.0")
processor = EventProcessor()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "sentinelstream"}


@app.post("/events")
def process_event(event: TelemetryEvent) -> dict:
    return processor.process(event)


@app.get("/events/recent")
def recent_events(
    limit: int = Query(default=100, ge=1, le=1000),
    metric: str | None = None,
    anomalies_only: bool = False,
) -> list[dict]:
    return processor.recent_events(
        limit=limit,
        metric=metric,
        anomalies_only=anomalies_only,
    )


@app.get("/events/stats")
def event_stats() -> dict:
    return processor.stats()
