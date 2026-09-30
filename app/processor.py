import hashlib
import json
from copy import deepcopy
from collections import OrderedDict, defaultdict, deque
from collections.abc import Mapping
from datetime import datetime, timedelta
from threading import RLock

from app.models import TelemetryEvent
from app.throughput import analyze_throughput


DEFAULT_THRESHOLDS: dict[str, tuple[float, float]] = {
    "temperature": (-40.0, 120.0),
    "pressure": (0.0, 250.0),
    "voltage": (0.0, 30.0),
}


class IdempotencyConflictError(ValueError):
    """Raised when an idempotency key is reused for another event payload."""


class EventProcessor:
    def __init__(
        self,
        thresholds: Mapping[str, tuple[float, float]] | None = None,
        history_size: int = 1000,
        deduplication_size: int = 5000,
        idempotency_size: int = 5000,
        source_cardinality_limit: int = 1000,
        stream_cardinality_limit: int = 5000,
    ) -> None:
        if history_size <= 0:
            raise ValueError("history_size must be greater than zero")
        if deduplication_size <= 0:
            raise ValueError("deduplication_size must be greater than zero")
        if idempotency_size <= 0:
            raise ValueError("idempotency_size must be greater than zero")
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
        self._event_keys: deque[tuple] = deque()
        self._event_key_set: set[tuple] = set()
        self._idempotency_size = idempotency_size
        self._idempotency_results: OrderedDict[str, tuple[tuple, dict]] = OrderedDict()
        self._lock = RLock()

    def process(self, event: TelemetryEvent) -> dict:
        with self._lock:
            metric = event.metric.lower()
            event_key = self._event_key(event)
            event_id = self._event_id(event_key)

            if event_key in self._event_key_set:
                self._duplicates += 1
                duplicate = {
                    "event_id": event_id,
                    "accepted": False,
                    "duplicate": True,
                    "source": event.source,
                    "metric": event.metric,
                    "value": event.value,
                    "timestamp": event.timestamp.isoformat(),
                }
                if event.correlation_id is not None:
                    duplicate["correlation_id"] = event.correlation_id
                return duplicate

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
                "event_id": event_id,
                "accepted": True,
                "duplicate": False,
                "anomaly": anomaly,
                "out_of_order": out_of_order,
                "source": event.source,
                "metric": event.metric,
                "value": event.value,
                "timestamp": event.timestamp.isoformat(),
            }
            if event.correlation_id is not None:
                result["correlation_id"] = event.correlation_id
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

    def process_idempotent(
        self,
        event: TelemetryEvent,
        idempotency_key: str,
    ) -> tuple[dict, bool]:
        """Process one event once for a bounded producer idempotency key."""
        fingerprint = (self._event_key(event),)
        with self._lock:
            replay = self._idempotency_replay(idempotency_key, fingerprint)
            if replay is not None:
                return replay, True
            result = self.process(event)
            self._remember_idempotency(idempotency_key, fingerprint, result)
            return deepcopy(result), False

    def process_many_idempotent(
        self,
        events: list[TelemetryEvent],
        idempotency_key: str,
    ) -> tuple[dict, bool]:
        """Process one batch once for a bounded producer idempotency key."""
        fingerprint = tuple(self._event_key(event) for event in events)
        with self._lock:
            replay = self._idempotency_replay(idempotency_key, fingerprint)
            if replay is not None:
                return replay, True
            result = self.process_many(events)
            self._remember_idempotency(idempotency_key, fingerprint, result)
            return deepcopy(result), False

    def recent_events(
        self,
        limit: int = 100,
        metric: str | None = None,
        source: str | None = None,
        correlation_id: str | None = None,
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
                if correlation_id is not None and item.get("correlation_id") != correlation_id:
                    continue
                if anomalies_only and not item["anomaly"]:
                    continue

                matches.append(item.copy())
                if len(matches) == limit:
                    break

        return matches

    def event_by_id(self, event_id: str) -> dict | None:
        """Find an accepted event within the bounded history window."""
        with self._lock:
            for item in reversed(self._recent_events):
                if item["event_id"] == event_id:
                    return item.copy()
        return None

    def event_context(
        self,
        event_id: str,
        before: int = 5,
        after: int = 5,
        same_stream: bool = False,
    ) -> dict | None:
        """Return a chronological window around one retained event."""
        if before < 0 or after < 0:
            raise ValueError("context window sizes cannot be negative")

        with self._lock:
            history = [item.copy() for item in self._recent_events]

        target = next(
            (item for item in history if item["event_id"] == event_id),
            None,
        )
        if target is None:
            return None

        if same_stream:
            history = [
                item
                for item in history
                if item["source"] == target["source"]
                and item["metric"].lower() == target["metric"].lower()
            ]

        target_index = next(
            index
            for index, item in enumerate(history)
            if item["event_id"] == event_id
        )
        start = max(0, target_index - before)
        end = min(len(history), target_index + after + 1)
        return {
            "event": target,
            "before": history[start:target_index],
            "after": history[target_index + 1 : end],
            "same_stream": same_stream,
            "has_more_before": start > 0,
            "has_more_after": end < len(history),
        }

    def correlation_summary(self, correlation_id: str) -> dict | None:
        """Summarize one correlated workflow within bounded event history."""
        with self._lock:
            events = [
                item.copy()
                for item in self._recent_events
                if item.get("correlation_id") == correlation_id
            ]

        if not events:
            return None

        timestamps = [datetime.fromisoformat(item["timestamp"]) for item in events]
        first_timestamp = min(timestamps)
        last_timestamp = max(timestamps)
        event_count = len(events)
        anomaly_count = sum(1 for item in events if item["anomaly"])
        out_of_order_count = sum(1 for item in events if item["out_of_order"])
        anomaly_rate = anomaly_count / event_count
        out_of_order_rate = out_of_order_count / event_count
        health_priority = {"healthy": 0, "watch": 1, "critical": 2}
        anomaly_health = self._source_health(anomaly_rate)
        ordering_health = self._ordering_health(out_of_order_rate)
        health = max(
            (anomaly_health, ordering_health),
            key=health_priority.__getitem__,
        )

        return {
            "correlation_id": correlation_id,
            "health": health,
            "event_count": event_count,
            "anomaly_count": anomaly_count,
            "anomaly_rate": anomaly_rate,
            "out_of_order_count": out_of_order_count,
            "out_of_order_rate": out_of_order_rate,
            "sources": sorted({item["source"] for item in events}),
            "metrics": sorted({item["metric"].lower() for item in events}),
            "first_timestamp": first_timestamp.isoformat(),
            "last_timestamp": last_timestamp.isoformat(),
            "duration_seconds": (last_timestamp - first_timestamp).total_seconds(),
        }

    def correlation_fault_analysis(self, correlation_id: str) -> dict | None:
        """Reconstruct observed fault propagation for one retained correlation."""
        with self._lock:
            events = [
                item.copy()
                for item in self._recent_events
                if item.get("correlation_id") == correlation_id
            ]

        if not events:
            return None

        streams: dict[tuple[str, str], dict] = {}
        fault_timeline: list[dict] = []
        for sequence, event in enumerate(events, start=1):
            stream_key = (event["source"], event["metric"].lower())
            stream = streams.setdefault(
                stream_key,
                {
                    "source": event["source"],
                    "metric": event["metric"].lower(),
                    "event_count": 0,
                    "anomaly_count": 0,
                    "ordering_fault_count": 0,
                    "first_fault_sequence": None,
                },
            )
            stream["event_count"] += 1
            stream["anomaly_count"] += int(event["anomaly"])
            stream["ordering_fault_count"] += int(event["out_of_order"])

            signals = []
            if event["anomaly"]:
                signals.append("anomaly")
            if event["out_of_order"]:
                signals.append("out_of_order")
            if not signals:
                continue

            if stream["first_fault_sequence"] is None:
                stream["first_fault_sequence"] = sequence
            fault_timeline.append(
                {
                    "sequence": sequence,
                    "event_id": event["event_id"],
                    "source": event["source"],
                    "metric": event["metric"],
                    "timestamp": event["timestamp"],
                    "signals": signals,
                }
            )

        stream_summaries = list(streams.values())
        stream_summaries.sort(
            key=lambda stream: (
                stream["first_fault_sequence"] is None,
                stream["first_fault_sequence"] or 0,
                stream["source"].casefold(),
                stream["metric"],
            )
        )
        return {
            "correlation_id": correlation_id,
            "status": "faults_detected" if fault_timeline else "healthy",
            "event_count": len(events),
            "fault_count": len(fault_timeline),
            "affected_stream_count": sum(
                stream["first_fault_sequence"] is not None
                for stream in stream_summaries
            ),
            "suspected_origin": fault_timeline[0] if fault_timeline else None,
            "fault_timeline": fault_timeline,
            "streams": stream_summaries,
        }

    def event_page(
        self,
        limit: int = 100,
        cursor: str | None = None,
        metric: str | None = None,
        source: str | None = None,
        correlation_id: str | None = None,
        anomalies_only: bool = False,
    ) -> dict:
        """Page through bounded history newest-first using a stable event ID cursor."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        normalized_metric = metric.lower() if metric is not None else None

        with self._lock:
            history = list(reversed(self._recent_events))

        start = 0
        if cursor is not None:
            for index, item in enumerate(history):
                if item["event_id"] == cursor:
                    start = index + 1
                    break
            else:
                raise KeyError("cursor not found in retained history")

        matches = []
        for item in history[start:]:
            if normalized_metric is not None and item["metric"].lower() != normalized_metric:
                continue
            if source is not None and item["source"] != source:
                continue
            if correlation_id is not None and item.get("correlation_id") != correlation_id:
                continue
            if anomalies_only and not item["anomaly"]:
                continue
            matches.append(item.copy())
            if len(matches) > limit:
                break

        has_more = len(matches) > limit
        events = matches[:limit]
        return {
            "events": events,
            "next_cursor": events[-1]["event_id"] if has_more else None,
            "has_more": has_more,
        }

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
                    "idempotency_keys": len(self._idempotency_results),
                    "idempotency_limit": self._idempotency_size,
                },
                "metrics": metrics,
                "sources": sources,
            }

    def _idempotency_replay(self, idempotency_key: str, fingerprint: tuple) -> dict | None:
        record = self._idempotency_results.get(idempotency_key)
        if record is None:
            return None
        recorded_fingerprint, result = record
        if recorded_fingerprint != fingerprint:
            raise IdempotencyConflictError(
                "idempotency key was already used for a different event payload"
            )
        self._idempotency_results.move_to_end(idempotency_key)
        return deepcopy(result)

    def _remember_idempotency(
        self,
        idempotency_key: str,
        fingerprint: tuple,
        result: dict,
    ) -> None:
        if len(self._idempotency_results) == self._idempotency_size:
            self._idempotency_results.popitem(last=False)
        self._idempotency_results[idempotency_key] = (fingerprint, deepcopy(result))

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

    def _remember_event_key(self, event_key: tuple) -> None:
        if len(self._event_keys) == self._deduplication_size:
            expired = self._event_keys.popleft()
            self._event_key_set.remove(expired)

        self._event_keys.append(event_key)
        self._event_key_set.add(event_key)

    @staticmethod
    def _event_key(event: TelemetryEvent) -> tuple:
        key = (
            event.source,
            event.metric.lower(),
            event.value,
            event.timestamp.isoformat(),
        )
        if event.correlation_id is not None:
            return (*key, event.correlation_id)
        return key

    @staticmethod
    def _event_id(event_key: tuple) -> str:
        canonical_event = json.dumps(
            event_key,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical_event.encode("utf-8")).hexdigest()

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
