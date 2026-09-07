from collections import defaultdict, deque
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
        history_size: int = 1000,
    ) -> None:
        if history_size <= 0:
            raise ValueError("history_size must be greater than zero")

        configured = thresholds if thresholds is not None else DEFAULT_THRESHOLDS
        self._thresholds = self._normalize_thresholds(configured)
        self._processed = 0
        self._anomalies = 0
        self._metric_counts: dict[str, int] = defaultdict(int)
        self._metric_anomalies: dict[str, int] = defaultdict(int)
        self._recent_events: deque[dict] = deque(maxlen=history_size)

    def process(self, event: TelemetryEvent) -> dict:
        metric = event.metric.lower()

        self._processed += 1
        self._metric_counts[metric] += 1

        anomaly = self._is_anomaly(event)
        if anomaly:
            self._anomalies += 1
            self._metric_anomalies[metric] += 1

        result = {
            "accepted": True,
            "anomaly": anomaly,
            "source": event.source,
            "metric": event.metric,
            "value": event.value,
            "timestamp": event.timestamp.isoformat(),
        }
        self._recent_events.append(result.copy())
        return result

    def recent_events(
        self,
        limit: int = 100,
        metric: str | None = None,
        anomalies_only: bool = False,
    ) -> list[dict]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        normalized_metric = metric.lower() if metric is not None else None
        matches: list[dict] = []

        for item in reversed(self._recent_events):
            if normalized_metric is not None and item["metric"].lower() != normalized_metric:
                continue
            if anomalies_only and not item["anomaly"]:
                continue

            matches.append(item.copy())
            if len(matches) == limit:
                break

        return matches

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
