from dataclasses import dataclass
import math
from numbers import Real


@dataclass(frozen=True)
class OffsetCommitReport:
    attempts: int
    failed_commits: int
    failure_rate_percent: float
    longest_failure_run: int
    status: str


def _validate_percent(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number")
    try:
        numeric_value = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(numeric_value):
        raise ValueError(f"{name} must be a finite number")
    return numeric_value


def analyze_offset_commits(
    commit_results: list[bool],
    warning_percent: float = 2.0,
    critical_percent: float = 10.0,
) -> OffsetCommitReport:
    warning_percent = _validate_percent(warning_percent, "warning_percent")
    critical_percent = _validate_percent(critical_percent, "critical_percent")
    if not 0 <= warning_percent < critical_percent <= 100:
        raise ValueError("thresholds must satisfy 0 <= warning < critical <= 100")
    if any(not isinstance(result, bool) for result in commit_results):
        raise ValueError("commit results must be booleans")
    if not commit_results:
        return OffsetCommitReport(0, 0, 0.0, 0, "no_data")

    failures = 0
    current_run = 0
    longest_run = 0
    for succeeded in commit_results:
        if succeeded:
            current_run = 0
            continue
        failures += 1
        current_run += 1
        longest_run = max(longest_run, current_run)

    rate = failures / len(commit_results) * 100.0
    if longest_run >= 3 or rate >= critical_percent:
        status = "critical"
    elif failures and rate >= warning_percent:
        status = "degraded"
    else:
        status = "healthy"

    return OffsetCommitReport(
        attempts=len(commit_results),
        failed_commits=failures,
        failure_rate_percent=round(rate, 2),
        longest_failure_run=longest_run,
        status=status,
    )
