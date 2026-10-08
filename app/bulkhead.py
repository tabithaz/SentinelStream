from threading import Lock


class InFlightLimiter:
    """Thread-safe non-blocking bulkhead for concurrent operations."""

    def __init__(self) -> None:
        self._in_flight = 0
        self._rejected = 0
        self._lock = Lock()

    def try_acquire(self, limit: int) -> bool:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        with self._lock:
            if self._in_flight >= limit:
                self._rejected += 1
                return False
            self._in_flight += 1
            return True

    def release(self) -> None:
        with self._lock:
            if self._in_flight <= 0:
                raise RuntimeError("cannot release an idle limiter")
            self._in_flight -= 1

    @property
    def in_flight(self) -> int:
        with self._lock:
            return self._in_flight

    def snapshot(self, limit: int) -> dict[str, int]:
        """Return an atomic, label-free view for operational metrics."""
        with self._lock:
            return {
                "limit": max(0, limit),
                "in_flight": self._in_flight,
                "rejected_total": self._rejected,
            }
