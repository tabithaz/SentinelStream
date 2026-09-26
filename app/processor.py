from collections import OrderedDict, defaultdict, deque
from datetime import datetime, timedelta
from collections.abc import Mapping
from threading import RLock

from app.models import TelemetryEvent
from app.throughput import analyze_throughput


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
        source_cardinality_limit: int = 1000,
        stream_cardinality_limit: int = 5000,
    ) -> None:
        if history_size <= 0:
            raise ValueError("history_size must be greater than zero")
        if deduplication_size <= 0:
            raise ValueError("deduplication_size must be greater than zero")
        if source_cardinality_limit <= 0:
            raise ValueError("source_cardinality_limit must be greater than zero")
        if stream_cardinality_limit <= 0:
            raise ValueError("stream_cardinality_limit must be greater than zero")

        configured = thresholds if thresholds is not None else DEFAULT_THRESHOLDS
        self._thresholds = self._normalize_thresholds(configured)
        self._processed = 0
        self._anomalies = 0
        self._duplicates = 0
        self._out_of_order = 0
        self._metric_counts: dict[str, int] = defaultdict(int)
        self._metric_anomalies: dict[str, int] = defaultdict(int)
        self._source_counts: dict[str, int] = defaultdict(int)
        self._source_anomalies: dict[str, int] = defaultdict(int)
        self._source_out_of_order: dict[str, int] = defaultdict(int)
        self._source_cardinality_limit = source_cardinality_limit
        self._source_overflow_events = 0
        self._source_overflow_anomalies = 0
        self._source_overflow_out_of_order = 0
        self._stream_cardinality_limit = stream_cardinality_limit
        self._latest_timestamps: OrderedDict[tuple[str, str], datetime] = OrderedDict()
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

            source_bucket = self._source_bucket(event.source)
            stream_key = (event.source, metric)
            latest_timestamp = self._latest_timestamps.get(stream_key)
            if latest_timestamp is not None:
                self._latest_timestamps.move_to_end(stream_key)
            out_of_order = latest_timestamp is not None and event.timestamp < latest_timestamp
            if out_of_order:
                self._out_of_order += 1
                if source_bucket is None:
                    self._source_overflow_out_of_order += 1
                else:
                    self._source_out_of_order[source_bucket] += 1
            elif latest_timestamp is None or event.timestamp > latest_timestamp:
                if (
                    latest_timestamp is None
                    and len(self._latest_timestamps) == self._stream_cardinality_limit
                ):
                    self._latest_timestamps.popitem(last=False)
                self._latest_timestamps[stream_key] = event.timestamp

            self._remember_event_key(event_key)
            self._processed += 1
            self._metric_counts[metric] += 1
            if source_bucket is None:
                self._source_overflow_events += 1
            else:
                self._source_counts[source_bucket] += 1

            anomaly = self._is_anomaly(event)
            if anomaly:
                self._anomalies += 1
                self._metric_anomalies[metric] += 1
                if source_bucket is None:
                    self._source_overflow_anomalies += 1
                else:
                    self._source_anomalies[source_bucket] += 1

            result = {
                "accepted": True,
                "duplicate": False,
                "anomaly": anomaly,
                "out_of_order": out_of_order,
                "source": event.source,
                "metric": event.metric,
                "value": event.value,
                "timestamp": event.timestamp.isoformat(),
            }
            self._recent_events.append(result.copy())
            return result

    def process_many(self, events: list[TelemetryEvent]) -> dict:
        if not events:
            raise ValueError("events must contain at least one telemetry event")
        if len(events) > 1000:
            raise ValueError("events cannot contain more than 1000 telemetry events")

        with self._lock:
            results = [self.process(event) for event in events]

        accepted = sum(1 for result in results if result["accepted"])
        duplicates = len(results) - accepted
        anomalies = sum(1 for result in results if result["accepted"] and result["anomaly"])
        out_of_order = sum(1 for result in results if result["accepted"] and result["out_of_order"])

        return {
            "received": len(results),
            "accepted": accepted,
            "duplicates": duplicates,
            "anomalies": anomalies,
            "out_of_order": out_of_order,
            "results": results,
        }

    def recent_events(
        self,
        limit: int = 100,
        metric: str | None = None,
        source: str | None = None,
        anomalies_only: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[dict]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if since is not None and until is not None and since > until:
            raise ValueError("since must be earlier than or equal to until")

        normalized_metric = metric.lower() if metric is not None else None
        matches: list[dict] = []

        with self._lock:
            for item in reversed(self._recent_events):
                timestamp = datetime.fromisoformat(item["timestamp"])
                if since is not None and timestamp < since:
                    continue
                if until is not None and timestamp > until:
                    continue
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

    def throughput_summary(
        self,
        window_seconds: int = 60,
        windows: int = 5,
        target_per_window: int = 100,
        source: str | None = None,
    ) -> dict:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")
        if windows <= 0:
            raise ValueError("windows must be greater than zero")

        with self._lock:
            events = [
                item.copy()
                for item in self._recent_events
                if source is None or item["source"] == source
            ]

        if not events:
            counts = [0] * windows
            analysis = analyze_throughput(counts, target_per_window)
            return {
                **analysis,
                "window_seconds": window_seconds,
                "window_counts": counts,
                "source": source,
                "anchor_timestamp": None,
            }

        timestamps = [datetime.fromisoformat(item["timestamp"]) for item in events]
        anchor = max(timestamps)
        horizon = timedelta(seconds=window_seconds * windows)
        counts = [0] * windows

        for timestamp in timestamps:
            age = anchor - timestamp
            if age < timedelta(0) or age >= horizon:
                continue

            windows_ago = int(age.total_seconds() // window_seconds)
            index = windows - 1 - windows_ago
            counts[index] += 1

        analysis = analyze_throughput(counts, target_per_window)
        return {
            **analysis,
            "window_seconds": window_seconds,
            "window_counts": counts,
            "source": source,
            "anchor_timestamp": anchor.isoformat(),
        }

    def ranked_sources(self, limit: int = 10) -> list[dict]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        with self._lock:
            ranked = []
            for source, count in self._source_counts.items():
                anomalies = self._source_anomalies[source]
                out_of_order = self._source_out_of_order[source]
                anomaly_rate = anomalies / count
                ordering_rate = out_of_order / count
                ranked.append(
                    {
                        "source": source,
                        "processed": count,
                        "anomalies": anomalies,
                        "anomaly_rate": anomaly_rate,
                        "health": self._source_health(anomaly_rate),
                        "out_of_order": out_of_order,
                        "out_of_order_rate": ordering_rate,
                        "ordering_health": self._ordering_health(ordering_rate),
                    }
                )

        ranked.sort(
            key=lambda item: (
                -item["anomaly_rate"],
                -item["out_of_order_rate"],
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
                out_of_order = self._source_out_of_order[source]
                anomaly_rate = anomalies / count
                ordering_rate = out_of_order / count
                sources[source] = {
                    "processed": count,
                    "anomalies": anomalies,
                    "anomaly_rate": anomaly_rate,
                    "health": self._source_health(anomaly_rate),
                    "out_of_order": out_of_order,
                    "out_of_order_rate": ordering_rate,
                    "ordering_health": self._ordering_health(ordering_rate),
                }

            return {
                "processed": self._processed,
                "anomalies": self._anomalies,
                "duplicates": self._duplicates,
                "out_of_order": self._out_of_order,
                "anomaly_rate": self._anomalies / self._processed if self._processed else 0.0,
                "out_of_order_rate": self._out_of_order / self._processed if self._processed else 0.0,
                "cardinality": {
                    "tracked_sources": len(self._source_counts),
                    "source_limit": self._source_cardinality_limit,
                    "source_overflow_events": self._source_overflow_events,
                    "source_overflow_anomalies": self._source_overflow_anomalies,
                    "source_overflow_out_of_order": self._source_overflow_out_of_order,
                    "tracked_streams": len(self._latest_timestamps),
                    "stream_limit": self._stream_cardinality_limit,
                },
                "metrics": metrics,
                "sources": sources,
            }

    def _source_bucket(self, source: str) -> str | None:
        if source in self._source_counts:
            return source
        if len(self._source_counts) < self._source_cardinality_limit:
            return source
        return None

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

    @staticmethod
    def _ordering_health(out_of_order_rate: float) -> str:
        if out_of_order_rate >= 0.25:
            return "critical"
        if out_of_order_rate >= 0.10:
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
                raise ValueError(f"invalid threshold for {metric!r}: minimum exceeds maximum")
            normalized[metric.lower()] = (minimum, maximum)

        return normalized
