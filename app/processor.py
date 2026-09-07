from collections import defaultdict
from collections.abc import Mapping

from app.models import TelemetryEvent


DEFAULT_THRESHOLDS: dict[str, tuple[float, float]] = {
    "temperature": (-40.0, 120.0),
    "pressure": (0.0, 250.0),
    "voltage": (0.0, 30.0),
}


class EventProcessor:
    def __init__(
        self,
        thresholds: Mapping[str, tuple[float, float]] | None = None,
    ) -> None:
        configured = thresholds if thresholds is not None else DEFAULT_THRESHOLDS
        self._thresholds = self._normalize_thresholds(configured)
        self._processed = 0
        self._anomalies = 0
        self._metric_counts: dict[str, int] = defaultdict(int)
        self._metric_anomalies: dict[str, int] = defaultdict(int)

    def process(self, event: TelemetryEvent) -> dict:
        metric = event.metric.lower()

        self._processed += 1
        self._metric_counts[metric] += 1

        anomaly = self._is_anomaly(event)
        if anomaly:
            self._anomalies += 1
            self._metric_anomalies[metric] += 1

        return {
            "accepted": True,
            "anomaly": anomaly,
            "source": event.source,
            "metric": event.metric,
            "value": event.value,
            "timestamp": event.timestamp.isoformat(),
        }

    def stats(self) -> dict:
        metrics = {
            metric: {
                "processed": count,
                "anomalies": self._metric_anomalies[metric],
                "anomaly_rate": self._metric_anomalies[metric] / count,
            }
            for metric, count in sorted(self._metric_counts.items())
        }

        return {
            "processed": self._processed,
            "anomalies": self._anomalies,
            "anomaly_rate": (
                self._anomalies / self._processed if self._processed else 0.0
            ),
            "metrics": metrics,
        }

    def _is_anomaly(self, event: TelemetryEvent) -> bool:
        bounds = self._thresholds.get(event.metric.lower())
        if bounds is None:
            return False

        minimum, maximum = bounds
        return not minimum <= event.value <= maximum

    @staticmethod
    def _normalize_thresholds(
        thresholds: Mapping[str, tuple[float, float]],
    ) -> dict[str, tuple[float, float]]:
        normalized: dict[str, tuple[float, float]] = {}

        for metric, bounds in thresholds.items():
            minimum, maximum = bounds
            if minimum > maximum:
                raise ValueError(
                    f"invalid threshold for {metric!r}: minimum exceeds maximum"
                )
            normalized[metric.lower()] = (minimum, maximum)

        return normalized
