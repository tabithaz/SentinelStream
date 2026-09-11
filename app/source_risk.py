from dataclasses import dataclass


@dataclass(frozen=True)
class SourceRisk:
    score: float
    level: str


def classify_source_risk(anomaly_rate: float, out_of_order_rate: float) -> SourceRisk:
    """Combine anomaly and ordering behavior into a source-level operational risk score."""
    for rate in (anomaly_rate, out_of_order_rate):
        if not 0.0 <= rate <= 1.0:
            raise ValueError("rates must be between 0 and 1")

    score = round(100.0 * ((0.7 * anomaly_rate) + (0.3 * out_of_order_rate)), 1)
    if score >= 50.0:
        level = "critical"
    elif score >= 20.0:
        level = "elevated"
    else:
        level = "normal"

    return SourceRisk(score=score, level=level)
