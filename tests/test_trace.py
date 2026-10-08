"""Round-trip tests for Trace JSON Lines persistence."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from tracker.trace import Span, Trace, append_trace, read_traces, trace_to_jsonl


def _span(
    *,
    component: str,
    span_input: dict | str,
    output: dict | str | None,
    started_at: datetime,
    latency_ms: float,
    success: bool,
    error: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
) -> Span:
    return Span(
        component=component,
        input=span_input,
        output=output,
        started_at=started_at,
        ended_at=started_at + timedelta(milliseconds=latency_ms),
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        success=success,
        error=error,
    )


def _trace(
    *,
    trace_id: str,
    trace_input: dict | str,
    final_output: dict | str | None,
    spans: list[Span],
    overall_success: bool,
) -> Trace:
    started_at = min(span.started_at for span in spans)
    ended_at = max(span.ended_at for span in spans)
    return Trace(
        trace_id=trace_id,
        pipeline_name="research_assistant",
        input=trace_input,
        final_output=final_output,
        spans=spans,
        started_at=started_at,
        ended_at=ended_at,
        total_latency_ms=sum(span.latency_ms for span in spans),
        total_cost_usd=sum(span.cost_usd or 0.0 for span in spans),
        overall_success=overall_success,
    )


def _sample_trace() -> Trace:
    t0 = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc)
    spans = [
        _span(
            component="generate_search_terms",
            span_input={"question": "What are the main agentic design patterns?"},
            output={"queries": ["agentic design patterns", "LLM agent workflows"]},
            started_at=t0,
            latency_ms=120.5,
            success=True,
            input_tokens=40,
            output_tokens=22,
            cost_usd=0.00021,
        ),
        _span(
            component="retrieve",
            span_input="agentic design patterns",
            output={"snippets": ["Reflection, tool use, planning, and multi-agent."]},
            started_at=t0 + timedelta(milliseconds=120.5),
            latency_ms=15.0,
            success=True,
        ),
        _span(
            component="synthesize_answer",
            span_input={
                "question": "What are the main agentic design patterns?",
                "snippets": ["Reflection, tool use, planning, and multi-agent."],
            },
            output=None,
            started_at=t0 + timedelta(milliseconds=135.5),
            latency_ms=80.25,
            success=False,
            error="empty synthesis",
            input_tokens=90,
            output_tokens=0,
            cost_usd=0.00045,
        ),
    ]
    return _trace(
        trace_id="4f3c1a2e-7b90-4d1e-8c55-0a1b2c3d4e5f",
        trace_input={"question": "What are the main agentic design patterns?"},
        final_output=None,
        spans=spans,
        overall_success=False,
    )


def test_trace_jsonl_round_trip() -> None:
    original = _sample_trace()

    line = trace_to_jsonl(original)

    assert "\n" not in line
    restored = Trace.model_validate_json(line)
    assert restored == original
    assert len(restored.spans) == 3
    assert [span.component for span in restored.spans] == [
        "generate_search_terms",
        "retrieve",
        "synthesize_answer",
    ]


def test_jsonl_file_preserves_all_fields(tmp_path: Path) -> None:
    path = tmp_path / "traces.jsonl"
    first = _sample_trace()
    second = _trace(
        trace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        trace_input="How do agents use tools?",
        final_output={"answer": "They call tools, observe results, and continue."},
        spans=[
            _span(
                component="generate_search_terms",
                span_input="How do agents use tools?",
                output="tool use query",
                started_at=datetime(2026, 10, 7, 13, 0, tzinfo=timezone.utc),
                latency_ms=10.0,
                success=True,
                input_tokens=8,
                output_tokens=4,
                cost_usd=0.00001,
            ),
            _span(
                component="retrieve",
                span_input={"queries": ["agent tool use"]},
                output={"snippets": []},
                started_at=datetime(2026, 10, 7, 13, 0, 1, tzinfo=timezone.utc),
                latency_ms=5.5,
                success=True,
                cost_usd=None,
            ),
        ],
        overall_success=True,
    )

    append_trace(path, first)
    append_trace(path, second)

    loaded = read_traces(path)

    assert loaded == [first, second]
    assert loaded[0].model_dump() == first.model_dump()
    assert loaded[1].model_dump() == second.model_dump()
