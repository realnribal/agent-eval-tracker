"""Pipeline produces a Trace with three spans and survives a failed LLM step."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from tracker.pipeline import run
from tracker.trace import Span, read_traces


def _ok_span(component: str, output: str) -> Span:
    now = datetime.now(timezone.utc)
    return Span(
        component=component,
        input="prompt",
        output=output,
        started_at=now,
        ended_at=now,
        latency_ms=12.0,
        input_tokens=20,
        output_tokens=10,
        cost_usd=0.0001,
        success=True,
        error=None,
    )


class _UnusedClient:
    messages = object()


class _RaisingMessages:
    def create(self, **kwargs: object) -> object:
        raise RuntimeError("overloaded")


class _RaisingClient:
    def __init__(self) -> None:
        self.messages = _RaisingMessages()


def test_full_run_with_mocked_llm_produces_a_trace_with_three_spans(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    responses = [
        _ok_span(
            "generate_search_terms",
            "agentic design patterns\nLLM agent workflows",
        ),
        _ok_span(
            "synthesize_answer",
            "The main patterns include reflection and tool use.",
        ),
    ]

    def fake_call(client, *, component, prompt, model, max_tokens):
        span = responses.pop(0)
        assert span.component == component
        return span

    monkeypatch.setattr("tracker.pipeline.call", fake_call)
    path = tmp_path / "traces.jsonl"

    trace = run(
        "What are the main agentic design patterns?",
        client=_UnusedClient(),
        traces_path=path,
    )

    assert len(trace.spans) == 3
    assert [span.component for span in trace.spans] == [
        "generate_search_terms",
        "retrieve",
        "synthesize_answer",
    ]
    assert all(span.success for span in trace.spans)
    assert trace.pipeline_name == "research_assistant"
    assert trace.input == {"question": "What are the main agentic design patterns?"}
    assert trace.final_output == "The main patterns include reflection and tool use."
    assert trace.overall_success is True
    assert trace.total_latency_ms == pytest.approx(sum(span.latency_ms for span in trace.spans))
    assert trace.total_cost_usd == pytest.approx(
        sum(span.cost_usd or 0.0 for span in trace.spans)
    )
    assert isinstance(trace.spans[1].output, dict)
    assert len(trace.spans[1].output["snippets"]) == 2
    assert read_traces(path) == [trace]


def test_raised_llm_error_does_not_crash_and_marks_span_failed(tmp_path: Path) -> None:
    path = tmp_path / "traces.jsonl"

    trace = run(
        "What are the main agentic design patterns?",
        client=_RaisingClient(),
        traces_path=path,
    )

    assert len(trace.spans) == 3
    assert trace.spans[0].component == "generate_search_terms"
    assert trace.spans[0].success is False
    assert "overloaded" in (trace.spans[0].error or "")
    assert trace.spans[1].component == "retrieve"
    assert trace.spans[1].success is True
    assert trace.spans[2].component == "synthesize_answer"
    assert trace.spans[2].success is False
    assert "overloaded" in (trace.spans[2].error or "")
    assert trace.overall_success is False
    assert trace.final_output is None
    assert read_traces(path) == [trace]


def test_empty_synthesis_makes_overall_success_false(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    responses = [
        _ok_span("generate_search_terms", "agentic design patterns"),
        _ok_span("synthesize_answer", "   "),
    ]

    def fake_call(client, *, component, prompt, model, max_tokens):
        return responses.pop(0)

    monkeypatch.setattr("tracker.pipeline.call", fake_call)

    trace = run(
        "What are the main agentic design patterns?",
        client=_UnusedClient(),
        traces_path=tmp_path / "traces.jsonl",
    )

    assert trace.spans[2].success is False
    assert trace.spans[2].error == "empty synthesis"
    assert trace.overall_success is False
    assert trace.final_output is None
