"""Trace and Span models, plus JSON Lines persistence."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel


class Span(BaseModel):
    component: str
    input: dict | str
    output: dict | str | None
    started_at: datetime
    ended_at: datetime
    latency_ms: float
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    success: bool
    error: str | None


class Trace(BaseModel):
    trace_id: str
    pipeline_name: str
    input: dict | str
    final_output: dict | str | None
    spans: list[Span]
    started_at: datetime
    ended_at: datetime
    total_latency_ms: float
    total_cost_usd: float
    overall_success: bool


def trace_to_jsonl(trace: Trace) -> str:
    """Serialize ``trace`` to one JSON Lines record, without a trailing newline."""
    return trace.model_dump_json()


def append_trace(path: str | Path, trace: Trace) -> None:
    """Append ``trace`` as a single JSON Lines record."""
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(trace_to_jsonl(trace))
        handle.write("\n")


def read_traces(path: str | Path) -> list[Trace]:
    """Read every Trace from a JSON Lines file. Blank lines are ignored."""
    traces: list[Trace] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            traces.append(Trace.model_validate_json(stripped))
    return traces
