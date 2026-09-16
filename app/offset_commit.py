from dataclasses import dataclass


@dataclass(frozen=True)
class OffsetCommitReport:
    attempts: int
    failed_commits: int
    failure_rate_percent: float
    longest_failure_run: int
    status: str


def analyze_offset_commits(
    commit_results: list[bool],
    warning_percent: float = 2.0,
    critical_percent: float = 10.0,
) -> OffsetCommitReport:
    if warning_percent < 0 or critical_percent <= warning_percent:
        raise ValueError("thresholds must satisfy 0 <= warning < critical")
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
