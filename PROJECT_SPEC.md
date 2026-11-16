# Build/Analyze Tracker — Project Spec

## 1. Goal

Build a small, portfolio-quality Python tool that demonstrates the **build ↔ analyze loop**
used when developing agentic AI systems (per Andrew Ng's "Agentic AI" course, DeepLearning.AI).

The tool wraps LLM calls inside a multi-step pipeline, logs every execution as a **structured
trace** (JSON), and generates an **error analysis report** showing failure rate per component.

This is an interview-grade demo project: it should be small, clean, well-tested, and the README
should explicitly explain the build/analyze concept it illustrates.

## 2. Tech stack

- Python 3.11+
- Anthropic API (`anthropic` SDK) — the LLM calls to wrap. (Can be swapped for OpenAI later;
  keep the LLM client behind an interface so the provider is not hardcoded.)
- `pydantic` for data models (Trace, Span)
- `click` or `typer` for the CLI
- `rich` for pretty terminal output of the error analysis report (optional but nice for a demo GIF)
- `pytest` for tests
- No web framework needed — this is a CLI tool, not a service.

## 3. Repository structure

```
build-analyze-tracker/
├── README.md
├── pyproject.toml
├── src/
│   └── tracker/
│       ├── __init__.py
│       ├── trace.py          # Trace & Span data models + JSON persistence
│       ├── llm_client.py      # Thin wrapper around the LLM API call (timing, cost, errors)
│       ├── pipeline.py        # Example agentic pipeline (see §5) instrumented with traces
│       ├── analysis.py        # Error analysis: aggregate failure rate per component
│       └── cli.py             # CLI entrypoints: `run`, `analyze`, `report`
├── traces/                    # JSON Lines output directory (gitignored, but keep a sample file)
│   └── sample_traces.jsonl
├── tests/
│   ├── test_trace.py
│   ├── test_llm_client.py
│   ├── test_pipeline.py
│   └── test_analysis.py
└── examples/
    └── demo_run.py             # Script used to record the demo GIF for LinkedIn
```

## 4. Data model

### Span
One instrumented step inside a pipeline run.

```python
class Span(BaseModel):
    component: str  # e.g. "search_term_generation", "retrieval", "synthesis"
    input: dict | str
    output: dict | str | None
    started_at: datetime
    ended_at: datetime
    latency_ms: float
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    success: bool  # did this component complete without error / pass its own check?
    error: str | None  # exception message if it failed
```

### Trace
One full end-to-end pipeline run.

```python
class Trace(BaseModel):
    trace_id: str  # uuid4
    pipeline_name: str
    input: dict | str
    final_output: dict | str | None
    spans: list[Span]
    started_at: datetime
    ended_at: datetime
    total_latency_ms: float
    total_cost_usd: float
    overall_success: bool  # did the end-to-end run succeed per the eval criterion?
```

Traces are persisted as **JSON Lines** (`traces/*.jsonl`), one Trace per line — this is the
simplest durable format and is easy to append to and to parse for analysis.

## 5. Example pipeline (the thing being instrumented)

Keep it simple and genuinely agentic so it's a credible demo, e.g. a 3-step **research assistant**:

1. `generate_search_terms` — LLM call: turn a user question into 2-3 search queries.
2. `retrieve` — call a (mocked or real) search/retrieval function with those queries.
3. `synthesize_answer` — LLM call: given the retrieved snippets, write the final answer.

Each step is wrapped by `llm_client.py` (for the LLM steps) and manually instrumented as a Span
for the retrieval step. Component-level success is defined per step (e.g. `synthesize_answer`
fails if the output is empty or doesn't cite any retrieved snippet — keep the check simple,
it's illustrative, not production-grade).

## 6. Core requirements

- `llm_client.call(...)` must measure wall-clock latency, capture input/output token counts from
  the API response, and compute `cost_usd` from a small hardcoded per-model pricing table.
- Every pipeline run must produce exactly one `Trace`, appended to `traces/traces.jsonl`.
- `analysis.py` must read all traces in a file and compute, **per component**:
  - number of calls
  - failure count & failure rate
  - average latency
  - average cost
- `cli.py report` prints this as a table (via `rich`) and can also export it as Markdown or JSON.
- Must handle and log API errors as a failed Span rather than crashing the whole run.

## 7. CLI

```
tracker run "What are the main agentic design patterns?"   # runs the pipeline once, logs a trace
tracker run --batch questions.txt                           # runs N inputs, logs N traces
tracker report traces/traces.jsonl                           # prints the error-analysis table
tracker report traces/traces.jsonl --format json             # for programmatic use
```

## 8. Tests

- `test_trace.py`: Trace/Span serialize/deserialize correctly to/from JSONL.
- `test_llm_client.py`: latency and cost are computed correctly (mock the API call).
- `test_pipeline.py`: a failing component produces a Span with `success=False` and the pipeline
  doesn't crash.
- `test_analysis.py`: given a fixture `traces.jsonl` with known failures, the aggregated
  failure-rate-per-component numbers are correct.

## 9. README requirements

The README must:
- Explain the build/analyze loop concept in 3-4 sentences, with a link back to the course.
- Show a sample output of `tracker report` (a markdown table or screenshot).
- Explain how to run it with your own Anthropic API key.
- Include a short "why this project" paragraph connecting it to real agentic-system debugging
  practice — this is the part that matters for an interview narrative.

## 10. Build order (suggested phases for Cursor/Claude Code to implement incrementally)

1. **Phase 1 — data model & persistence**: `trace.py` + its tests. No LLM calls yet.
2. **Phase 2 — LLM client wrapper**: `llm_client.py` with timing/cost/error handling + tests
   (mock the Anthropic client in tests, don't hit the real API in CI).
3. **Phase 3 — example pipeline**: `pipeline.py` wired to produce a real Trace from a real run.
4. **Phase 4 — error analysis**: `analysis.py` + tests against a fixture traces file.
5. **Phase 5 — CLI**: `cli.py` tying it all together.
6. **Phase 6 — polish**: README, sample traces file, demo script for the GIF.

Ask Cursor to implement **one phase at a time** and to run the tests before moving to the next
phase — this mirrors the build/analyze discipline the project itself is meant to demonstrate.

## 11. Stretch goals (optional, after v1 works)

- A `--component` filter on `report` to drill into one component's failures only.
- A tiny `rich`-based bar chart of failure rate per component in the terminal.
- Swap in an LLM-as-judge for `overall_success` instead of a hardcoded heuristic.

## 12. Phase 7 — stretch: LangChain integration

### Goal
Demonstrate that the same tracker can instrument a pipeline built with a standard framework
(LangChain), not just hand-written LLM calls. This shows the ability to add observability
to pre-existing agentic code — a realistic enterprise scenario — rather than only building
from scratch.

### Scope
- Do NOT rewrite the existing pipeline (`pipeline.py`). This phase adds a **second, separate
  pipeline** (e.g. `pipeline_langchain.py`) that reimplements the same 3-step research
  assistant (generate_search_terms → retrieve → synthesize_answer) using LangChain's
  `LCEL` (LangChain Expression Language) or a simple `Runnable` chain.
- Implement a custom `BaseCallbackHandler` (LangChain's hook mechanism for observing chain
  execution) that converts LangChain's `on_chain_start` / `on_chain_end` / `on_llm_start` /
  `on_llm_end` / `on_chain_error` events into the existing `Span` and `Trace` pydantic models
  from `trace.py`. No changes to the Trace/Span schema — the callback handler is the adapter.
- The callback handler must capture the same fields as the native pipeline: component name
  (from the chain/step name), input, output, latency, token usage (available on
  `on_llm_end`'s `response.llm_output`), success/failure, and error message on
  `on_chain_error`.
- Traces produced this way are appended to the **same** `traces/traces.jsonl` file, using the
  same format — so `tracker report` and `analysis.py` work unmodified on both sources. This
  is the key proof point: the observability layer is decoupled from how the pipeline itself
  is built.

### New dependencies
- `langchain` and `langchain-anthropic` (or `langchain-core` if you want the lighter-weight
  LCEL-only package instead of the full framework).

### CLI addition
```
tracker run --engine langchain "What are the main agentic design patterns?"
tracker run --engine native "..."     # existing Phase 3 pipeline, now explicit via a flag
```

### Tests
- `test_pipeline_langchain.py`: running the LangChain pipeline produces a valid Trace with the
  expected number of Spans, and a failing step is captured as `success=False` rather than
  raising unhandled out of the callback handler.
- A shared test asserting that `analysis.py`'s aggregation logic produces identical output
  structure regardless of whether the traces came from the native or the LangChain pipeline.

### README addition
A short paragraph explaining the point of this phase explicitly: "the same observability
format works whether the agentic pipeline is hand-rolled or built with a framework like
LangChain — this mirrors a common real-world task: adding error analysis and cost tracking
to an existing LangChain-based system." This is the sentence you'll reuse almost verbatim
in an interview.

### Order
Implement this only after Phases 1-6 are complete and `tracker report` works end-to-end on
native traces. This phase is additive and should never block or modify the native pipeline.
