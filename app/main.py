from fastapi import FastAPI

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


@app.get("/events/stats")
def event_stats() -> dict:
    return processor.stats()
