"""Three-step research assistant that records one Trace per run."""

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from tracker.llm_client import SupportsMessages, call
from tracker.trace import Span, Trace, append_trace

PIPELINE_NAME = "research_assistant"
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_TRACES_PATH = Path("traces/traces.jsonl")

_FAKE_SNIPPETS = [
    "Reflection: the agent critiques its own draft and revises.",
    "Tool use: the agent calls search or code tools and reads the results.",
]


def run(
    question: str,
    *,
    client: SupportsMessages,
    model: str = DEFAULT_MODEL,
    traces_path: str | Path = DEFAULT_TRACES_PATH,
) -> Trace:
    """Run the research assistant once, append one Trace, and return it."""
    spans: list[Span] = []

    terms_span = call(
        client,
        component="generate_search_terms",
        prompt=_search_terms_prompt(question),
        model=model,
        max_tokens=256,
    )
    spans.append(terms_span)
    queries = _parse_queries(terms_span.output) if terms_span.success else []

    retrieve_span = _retrieve(queries)
    spans.append(retrieve_span)
    snippets = (
        list(retrieve_span.output["snippets"])
        if retrieve_span.success and isinstance(retrieve_span.output, dict)
        else []
    )

    synth_span = call(
        client,
        component="synthesize_answer",
        prompt=_synthesize_prompt(question, snippets),
        model=model,
        max_tokens=512,
    )
    if synth_span.success and not _non_empty_text(synth_span.output):
        synth_span = synth_span.model_copy(
            update={"success": False, "error": "empty synthesis"}
        )
    spans.append(synth_span)

    final_output = synth_span.output if synth_span.success else None
    overall_success = synth_span.success and _non_empty_text(final_output)
    started_at = min(span.started_at for span in spans)
    ended_at = max(span.ended_at for span in spans)
    trace = Trace(
        trace_id=str(uuid.uuid4()),
        pipeline_name=PIPELINE_NAME,
        input={"question": question},
        final_output=final_output,
        spans=spans,
        started_at=started_at,
        ended_at=ended_at,
        total_latency_ms=sum(span.latency_ms for span in spans),
        total_cost_usd=sum(span.cost_usd or 0.0 for span in spans),
        overall_success=overall_success,
    )

    path = Path(traces_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    append_trace(path, trace)
    return trace


def _retrieve(queries: list[str]) -> Span:
    """Stubbed search: always returns a couple of fake snippets."""
    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    snippets = list(_FAKE_SNIPPETS)
    latency_ms = (time.perf_counter() - started) * 1000
    return Span(
        component="retrieve",
        input={"queries": queries},
        output={"snippets": snippets},
        started_at=started_at,
        ended_at=datetime.now(timezone.utc),
        latency_ms=latency_ms,
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,
        success=True,
        error=None,
    )


def _parse_queries(output: dict | str | None) -> list[str]:
    if not isinstance(output, str):
        return []
    queries: list[str] = []
    for line in output.splitlines():
        cleaned = line.strip().lstrip("-*").strip()
        cleaned = cleaned.lstrip("0123456789.").strip()
        if cleaned:
            queries.append(cleaned)
    return queries[:3]


def _non_empty_text(value: dict | str | None) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _search_terms_prompt(question: str) -> str:
    return (
        "Turn the user question into 2 or 3 short search queries.\n"
        "Return only the queries, one per line.\n\n"
        f"Question: {question}"
    )


def _synthesize_prompt(question: str, snippets: list[str]) -> str:
    joined = "\n".join(f"- {snippet}" for snippet in snippets) or "- (none)"
    return (
        "Answer the question using the retrieved snippets.\n"
        "Quote or reuse wording from at least one snippet.\n\n"
        f"Question: {question}\n\n"
        f"Snippets:\n{joined}"
    )
