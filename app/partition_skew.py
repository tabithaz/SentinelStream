from dataclasses import dataclass


@dataclass(frozen=True)
class PartitionSkew:
    partitions: int
    total_events: int
    hottest_partition: str | None
    hottest_share: float
    imbalance_ratio: float
    status: str


def analyze_partition_skew(partition_counts: dict[str, int]) -> PartitionSkew:
    if any(count < 0 for count in partition_counts.values()):
        raise ValueError("partition counts cannot be negative")
    if not partition_counts:
        return PartitionSkew(0, 0, None, 0.0, 0.0, "no_data")

    total = sum(partition_counts.values())
    if total == 0:
        return PartitionSkew(len(partition_counts), 0, None, 0.0, 0.0, "idle")

    hottest_partition, hottest_count = min(
        partition_counts.items(), key=lambda item: (-item[1], item[0])
    )
    average = total / len(partition_counts)
    imbalance_ratio = hottest_count / average
    hottest_share = hottest_count / total

    if imbalance_ratio >= 2.0 or hottest_share >= 0.6:
        status = "critical"
    elif imbalance_ratio >= 1.5 or hottest_share >= 0.4:
        status = "skewed"
    else:
        status = "balanced"

    return PartitionSkew(
        partitions=len(partition_counts),
        total_events=total,
        hottest_partition=hottest_partition,
        hottest_share=round(hottest_share, 4),
        imbalance_ratio=round(imbalance_ratio, 4),
        status=status,
    )
