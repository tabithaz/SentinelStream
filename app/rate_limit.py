from collections import OrderedDict, deque
from dataclasses import dataclass
import math
from threading import RLock


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class SlidingWindowRateLimiter:
    """Thread-safe, cardinality-bounded sliding-window rate limiter."""

    def __init__(self, window_seconds: float = 60.0, max_identities: int = 10_000) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")
        if max_identities <= 0:
            raise ValueError("max_identities must be greater than zero")
        self._window_seconds = window_seconds
        self._max_identities = max_identities
        self._requests: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = RLock()

    def check(self, identity: str, limit: int, now: float) -> RateLimitDecision:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        with self._lock:
            timestamps = self._requests.get(identity)
            if timestamps is None:
                if len(self._requests) == self._max_identities:
                    self._requests.popitem(last=False)
                timestamps = deque()
                self._requests[identity] = timestamps
            else:
                self._requests.move_to_end(identity)

            cutoff = now - self._window_seconds
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= limit:
                retry_after = max(
                    1,
                    math.ceil(timestamps[0] + self._window_seconds - now),
                )
                return RateLimitDecision(False, 0, retry_after)

            timestamps.append(now)
            return RateLimitDecision(True, limit - len(timestamps), 0)

    @property
    def identity_count(self) -> int:
        with self._lock:
            return len(self._requests)
