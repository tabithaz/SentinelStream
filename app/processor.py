from collections import defaultdict, deque
from collections.abc import Mapping
from threading import RLock

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
        deduplication_size: int = 5000,
    ) -> None:
        if history_size <= 0:
            raise ValueError("history_size must be greater than zero")
        if deduplication_size <= 0:
            raise ValueError("deduplication_size must be greater than zero")

        configured = thresholds if thresholds is not None else DEFAULT_THRESHOLDS
        self._thresholds = self._normalize_thresholds(configured)
        self._processed = 0
        self._anomalies = 0
        self._duplicates = 0
        self._metric_counts: dict[str, int] = defaultdict(int)
        self._metric_anomalies: dict[str, int] = defaultdict(int)
        self._source_counts: dict[str, int] = defaultdict(int)
        self._source_anomalies: dict[str, int] = defaultdict(int)
        self._recent_events: deque[dict] = deque(maxlen=history_size)
        self._deduplication_size = deduplication_size
        self._event_keys: deque[tuple[str, str, float, str]] = deque()
        self._event_key_set: set[tuple[str, str, float, str]] = set()
        self._lock = RLock()

    def process(self, event: TelemetryEvent) -> dict:
        with self._lock:
            metric = event.metric.lower()
            event_key = self._event_key(event)

            if event_key in self._event_key_set:
                self._duplicates += 1
                return {
                    "accepted": False,
                    "duplicate": True,
                    "source": event.source,
                    "metric": event.metric,
                    "value": event.value,
                    "timestamp": event.timestamp.isoformat(),
                }

            self._remember_event_key(event_key)
            self._processed += 1
            self._metric_counts[metric] += 1
            self._source_counts[event.source] += 1

            anomaly = self._is_anomaly(event)
            if anomaly:
                self._anomalies += 1
                self._metric_anomalies[metric] += 1
                self._source_anomalies[event.source] += 1

            result = {
                "accepted": True,
                "duplicate": False,
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
        source: str | None = None,
        anomalies_only: bool = False,
    ) -> list[dict]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        normalized_metric = metric.lower() if metric is not None else None
        matches: list[dict] = []

        with self._lock:
            for item in reversed(self._recent_events):
                if normalized_metric is not None and item["metric"].lower() != normalized_metric:
                    continue
                if source is not None and item["source"] != source:
                    continue
                if anomalies_only and not item["anomaly"]:
                    continue

                matches.append(item.copy())
                if len(matches) == limit:
                    break

        return matches

    def ranked_sources(self, limit: int = 10) -> list[dict]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        with self._lock:
            ranked = []
            for source, count in self._source_counts.items():
                anomalies = self._source_anomalies[source]
                anomaly_rate = anomalies / count
                ranked.append(
                    {
                        "source": source,
                        "processed": count,
                        "anomalies": anomalies,
                        "anomaly_rate": anomaly_rate,
                        "health": self._source_health(anomaly_rate),
                    }
                )

        ranked.sort(
            key=lambda item: (
                -item["anomaly_rate"],
                -item["anomalies"],
                -item["processed"],
                item["source"],
            )
        )
        return ranked[:limit]

    def ranked_metrics(self, limit: int = 10) -> list[dict]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        with self._lock:
            ranked = []
            for metric, count in self._metric_counts.items():
                anomalies = self._metric_anomalies[metric]
                anomaly_rate = anomalies / count
                ranked.append(
                    {
                        "metric": metric,
                        "processed": count,
                        "anomalies": anomalies,
                        "anomaly_rate": anomaly_rate,
                        "health": self._source_health(anomaly_rate),
                    }
                )

        ranked.sort(
            key=lambda item: (
                -item["anomaly_rate"],
                -item["anomalies"],
                -item["processed"],
                item["metric"],
            )
        )
        return ranked[:limit]

    def stats(self) -> dict:
        with self._lock:
            metrics = {
                metric: {
                    "processed": count,
                    "anomalies": self._metric_anomalies[metric],
                    "anomaly_rate": self._metric_anomalies[metric] / count,
                }
                for metric, count in sorted(self._metric_counts.items())
            }
            sources = {}
            for source, count in sorted(self._source_counts.items()):
                anomalies = self._source_anomalies[source]
                anomaly_rate = anomalies / count
                sources[source] = {
                    "processed": count,
                    "anomalies": anomalies,
                    "anomaly_rate": anomaly_rate,
                    "health": self._source_health(anomaly_rate),
                }

            return {
                "processed": self._processed,
                "anomalies": self._anomalies,
                "duplicates": self._duplicates,
                "anomaly_rate": (
                    self._anomalies / self._processed if self._processed else 0.0
                ),
                "metrics": metrics,
                "sources": sources,
            }

    def _is_anomaly(self, event: TelemetryEvent) -> bool:
        bounds = self._thresholds.get(event.metric.lower())
        if bounds is None:
            return False

        minimum, maximum = bounds
        return not minimum <= event.value <= maximum

    @staticmethod
    def _source_health(anomaly_rate: float) -> str:
        if anomaly_rate >= 0.5:
            return "critical"
        if anomaly_rate >= 0.2:
            return "watch"
        return "healthy"

    def _remember_event_key(self, event_key: tuple[str, str, float, str]) -> None:
        if len(self._event_keys) == self._deduplication_size:
            expired = self._event_keys.popleft()
            self._event_key_set.remove(expired)

        self._event_keys.append(event_key)
        self._event_key_set.add(event_key)

    @staticmethod
    def _event_key(event: TelemetryEvent) -> tuple[str, str, float, str]:
        return (
            event.source,
            event.metric.lower(),
            event.value,
            event.timestamp.isoformat(),
        )

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
