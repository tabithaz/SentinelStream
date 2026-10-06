from collections import defaultdict
from threading import Lock


REQUEST_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)


class RequestMetrics:
    """Thread-safe, bounded HTTP RED metrics keyed by application route."""

    def __init__(self) -> None:
        self._requests: dict[tuple[str, str, int], int] = defaultdict(int)
        self._duration_count: dict[tuple[str, str], int] = defaultdict(int)
        self._duration_sum: dict[tuple[str, str], float] = defaultdict(float)
        self._duration_buckets: dict[tuple[str, str], list[int]] = {}
        self._in_flight = 0
        self._lock = Lock()

    def begin(self) -> None:
        with self._lock:
            self._in_flight += 1

    def observe(
        self,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        key = (method, route)
        with self._lock:
            self._requests[(method, route, status_code)] += 1
            self._duration_count[key] += 1
            self._duration_sum[key] += duration_seconds
            buckets = self._duration_buckets.setdefault(
                key,
                [0 for _ in REQUEST_DURATION_BUCKETS],
            )
            for index, boundary in enumerate(REQUEST_DURATION_BUCKETS):
                if duration_seconds <= boundary:
                    buckets[index] += 1
            self._in_flight = max(0, self._in_flight - 1)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "in_flight": self._in_flight,
                "requests": dict(self._requests),
                "duration_count": dict(self._duration_count),
                "duration_sum": dict(self._duration_sum),
                "duration_buckets": {
                    key: list(counts)
                    for key, counts in self._duration_buckets.items()
                },
            }


def _label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def render_prometheus_metrics(stats: dict, requests: dict | None = None) -> str:
    received = stats["processed"] + stats["duplicates"]
    metrics = (
        (
            "sentinelstream_events_received_total",
            "Telemetry events received, including rejected duplicates.",
            "counter",
            received,
        ),
        (
            "sentinelstream_events_processed_total",
            "Telemetry events accepted for processing.",
            "counter",
            stats["processed"],
        ),
        (
            "sentinelstream_events_duplicate_total",
            "Telemetry events rejected as duplicate deliveries.",
            "counter",
            stats["duplicates"],
        ),
        (
            "sentinelstream_events_anomaly_total",
            "Accepted telemetry events classified as anomalous.",
            "counter",
            stats["anomalies"],
        ),
        (
            "sentinelstream_events_out_of_order_total",
            "Accepted telemetry events received out of order.",
            "counter",
            stats["out_of_order"],
        ),
        (
            "sentinelstream_event_anomaly_ratio",
            "Ratio of anomalous events among accepted events.",
            "gauge",
            stats["anomaly_rate"],
        ),
        (
            "sentinelstream_event_out_of_order_ratio",
            "Ratio of out-of-order events among accepted events.",
            "gauge",
            stats["out_of_order_rate"],
        ),
        (
            "sentinelstream_sources_monitored",
            "Number of telemetry sources observed by this process.",
            "gauge",
            len(stats["sources"]),
        ),
        (
            "sentinelstream_metrics_monitored",
            "Number of telemetry metric names observed by this process.",
            "gauge",
            len(stats["metrics"]),
        ),
    )

    lines: list[str] = []
    for name, help_text, metric_type, value in metrics:
        lines.extend(
            (
                f"# HELP {name} {help_text}",
                f"# TYPE {name} {metric_type}",
                f"{name} {value:.15g}",
            )
        )
    if requests is not None:
        lines.extend((
            "# HELP sentinelstream_http_requests_total Completed HTTP requests by route and status.",
            "# TYPE sentinelstream_http_requests_total counter",
        ))
        for (method, route, status), count in sorted(requests["requests"].items()):
            lines.append(
                'sentinelstream_http_requests_total'
                f'{{method="{_label(method)}",route="{_label(route)}",status="{status}"}} {count}'
            )
        lines.extend((
            "# HELP sentinelstream_http_request_duration_seconds HTTP request latency by route.",
            "# TYPE sentinelstream_http_request_duration_seconds histogram",
        ))
        for (method, route), count in sorted(requests["duration_count"].items()):
            labels = f'method="{_label(method)}",route="{_label(route)}"'
            for boundary, bucket_count in zip(
                REQUEST_DURATION_BUCKETS,
                requests["duration_buckets"][(method, route)],
            ):
                lines.append(
                    "sentinelstream_http_request_duration_seconds_bucket"
                    f'{{{labels},le="{boundary:g}"}} {bucket_count}'
                )
            lines.append(
                "sentinelstream_http_request_duration_seconds_bucket"
                f'{{{labels},le="+Inf"}} {count}'
            )
            lines.append(
                "sentinelstream_http_request_duration_seconds_sum"
                f'{{{labels}}} {requests["duration_sum"][(method, route)]:.15g}'
            )
            lines.append(
                "sentinelstream_http_request_duration_seconds_count"
                f'{{{labels}}} {count}'
            )
        lines.extend((
            "# HELP sentinelstream_http_requests_in_flight HTTP requests currently executing.",
            "# TYPE sentinelstream_http_requests_in_flight gauge",
            f'sentinelstream_http_requests_in_flight {requests["in_flight"]}',
        ))
    return "\n".join(lines) + "\n"
