from datetime import datetime

from pydantic import BaseModel, Field


class TelemetryEvent(BaseModel):
    source: str = Field(min_length=1, max_length=100)
    metric: str = Field(min_length=1, max_length=100)
    value: float
    timestamp: datetime
