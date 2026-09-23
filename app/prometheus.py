def render_prometheus_metrics(stats: dict) -> str:
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
    return "\n".join(lines) + "\n"
