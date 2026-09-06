from collections import defaultdict

from app.models import TelemetryEvent


class EventProcessor:
    def __init__(self) -> None:
        self._processed = 0
        self._anomalies = 0
        self._metric_counts: dict[str, int] = defaultdict(int)

    def process(self, event: TelemetryEvent) -> dict:
        self._processed += 1
        self._metric_counts[event.metric] += 1

        anomaly = self._is_anomaly(event)
        if anomaly:
            self._anomalies += 1

        return {
            "accepted": True,
            "anomaly": anomaly,
            "source": event.source,
            "metric": event.metric,
            "value": event.value,
            "timestamp": event.timestamp.isoformat(),
        }

    def stats(self) -> dict[str, int]:
        return {
            "processed": self._processed,
            "anomalies": self._anomalies,
        }

    @staticmethod
    def _is_anomaly(event: TelemetryEvent) -> bool:
        thresholds = {
            "temperature": (-40.0, 120.0),
            "pressure": (0.0, 250.0),
            "voltage": (0.0, 30.0),
        }

        bounds = thresholds.get(event.metric.lower())
        if bounds is None:
            return False

        minimum, maximum = bounds
        return not minimum <= event.value <= maximum
