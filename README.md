# agent-eval-tracker

A small CLI that runs a three-step research assistant, stores each run as a structured
trace, and reports failure rate, latency, and cost per component.

## The build and analyze loop

[Agentic AI](https://www.deeplearning.ai/courses/agentic-ai) (Andrew Ng, DeepLearning.AI)
treats agent work as a loop: build a pipeline, run it, see which step failed, change that
step, run again. A final answer alone cannot name the failed step. This tool writes one
`Trace` per run (with a `Span` per component) to a JSON Lines file, then aggregates those
spans so you can see where to edit next.

## Why this project

When an agentic pipeline misbehaves in practice, the bug is usually in one component:
bad search terms, empty retrieval, or a weak synthesis. Logging only the final string
hides that. Spans with `success` and `error` make the failure countable across runs, so
the next change targets the component with the highest failure rate instead of guesswork.

## Setup

Python 3.11 or newer. Install with [uv](https://github.com/astral-sh/uv):

```bash
uv sync
```

Set your Anthropic API key (the client reads only `ANTHROPIC_API_KEY`):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Or copy `.env.example` to `.env` and export the variable before you run the CLI.
Do not commit `.env`.

## Run the pipeline

```bash
uv run tracker run "What are the main agentic design patterns?"
uv run tracker run --batch questions.txt
```

Each run appends one line to `traces/traces.jsonl`.

## Report failures per component

```bash
uv run tracker report traces/sample_traces.jsonl
uv run tracker report traces/sample_traces.jsonl --format markdown
uv run tracker report traces/sample_traces.jsonl --format json
```

Sample output (`--format markdown` on the checked-in sample file):

| component | calls | failures | failure_rate | avg_latency_ms | avg_cost_usd |
| --- | ---: | ---: | ---: | ---: | ---: |
| generate_search_terms | 3 | 1 | 33.3% | 100.0 | 0.000200 |
| retrieve | 3 | 0 | 0.0% | 13.3 | 0.000000 |
| synthesize_answer | 3 | 2 | 66.7% | 166.7 | 0.000467 |

Here `synthesize_answer` fails most often, so that is the step to inspect first.

## Demo script

For a recording or a quick end-to-end check:

```bash
uv run python examples/demo_run.py
```

## Tests

```bash
uv run pytest
```

Tests mock the Anthropic client. They do not call the real API.

## Layout

- `src/tracker/trace.py` — `Span` / `Trace` and JSON Lines helpers
- `src/tracker/llm_client.py` — timed Anthropic call that returns a `Span`
- `src/tracker/pipeline.py` — research assistant (`generate_search_terms` → `retrieve` → `synthesize_answer`)
- `src/tracker/analysis.py` — per-component aggregates
- `src/tracker/cli.py` — `tracker run` and `tracker report`
- `traces/sample_traces.jsonl` — sample traces for `tracker report`
- `examples/demo_run.py` — short demo used for GIFs
