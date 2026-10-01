from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator, model_validator


class TelemetryEvent(BaseModel):
    source: str = Field(min_length=1, max_length=100)
    metric: str = Field(min_length=1, max_length=100)
    correlation_id: str | None = Field(default=None, min_length=1, max_length=100)
    value: float = Field(allow_inf_nan=False)
    timestamp: datetime

    @field_validator("source", "metric", "correlation_id", mode="before")
    @classmethod
    def normalize_identifier(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(timezone.utc)


class ThresholdBounds(BaseModel):
    minimum: float = Field(allow_inf_nan=False)
    maximum: float = Field(allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_range(self) -> "ThresholdBounds":
        if self.minimum > self.maximum:
            raise ValueError("minimum cannot exceed maximum")
        return self


class ThresholdConfiguration(BaseModel):
    thresholds: dict[str, ThresholdBounds] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def normalize_metrics(self) -> "ThresholdConfiguration":
        normalized: dict[str, ThresholdBounds] = {}
        for metric, bounds in self.thresholds.items():
            name = metric.strip().lower()
            if not name:
                raise ValueError("metric names must not be blank")
            if len(name) > 100:
                raise ValueError("metric names cannot exceed 100 characters")
            if name in normalized:
                raise ValueError("metric names must be unique ignoring case")
            normalized[name] = bounds
        self.thresholds = normalized
        return self
