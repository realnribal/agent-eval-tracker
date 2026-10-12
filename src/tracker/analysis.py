"""Per-component failure rates, latency, and cost from Trace JSON Lines."""

from pathlib import Path

from pydantic import BaseModel

from tracker.trace import Trace, read_traces


class ComponentStats(BaseModel):
    component: str
    calls: int
    failures: int
    failure_rate: float
    avg_latency_ms: float
    avg_cost_usd: float


def analyze(path: str | Path) -> list[ComponentStats]:
    """Aggregate span metrics by component name, sorted by component."""
    return analyze_traces(read_traces(path))


def analyze_traces(traces: list[Trace]) -> list[ComponentStats]:
    """Aggregate span metrics from in-memory traces, sorted by component."""
    totals: dict[str, _Bucket] = {}
    for trace in traces:
        for span in trace.spans:
            bucket = totals.setdefault(span.component, _Bucket())
            bucket.calls += 1
            if not span.success:
                bucket.failures += 1
            bucket.latency_ms += span.latency_ms
            bucket.cost_usd += span.cost_usd or 0.0

    stats = [
        ComponentStats(
            component=name,
            calls=bucket.calls,
            failures=bucket.failures,
            failure_rate=bucket.failures / bucket.calls,
            avg_latency_ms=bucket.latency_ms / bucket.calls,
            avg_cost_usd=bucket.cost_usd / bucket.calls,
        )
        for name, bucket in totals.items()
    ]
    return sorted(stats, key=lambda item: item.component)


class _Bucket:
    def __init__(self) -> None:
        self.calls = 0
        self.failures = 0
        self.latency_ms = 0.0
        self.cost_usd = 0.0
