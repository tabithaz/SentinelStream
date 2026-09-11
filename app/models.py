from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class TelemetryEvent(BaseModel):
    source: str = Field(min_length=1, max_length=100)
    metric: str = Field(min_length=1, max_length=100)
    value: float
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)
