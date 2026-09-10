def classify_stream_reliability(
    *, anomaly_rate: float, duplicate_rate: float, out_of_order_rate: float
) -> dict[str, float | str]:
    """Combine three stream-quality signals into a single reliability score."""
    for name, rate in {
        "anomaly_rate": anomaly_rate,
        "duplicate_rate": duplicate_rate,
        "out_of_order_rate": out_of_order_rate,
    }.items():
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1")

    weighted_fault_rate = (
        anomaly_rate * 0.50
        + duplicate_rate * 0.30
        + out_of_order_rate * 0.20
    )
    score = round((1.0 - weighted_fault_rate) * 100.0, 1)

    if score >= 90.0:
        status = "reliable"
    elif score >= 75.0:
        status = "degraded"
    else:
        status = "unreliable"

    return {"score": score, "status": status}
