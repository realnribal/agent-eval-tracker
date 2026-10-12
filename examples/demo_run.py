"""Demo script for recording a short CLI walkthrough GIF.

Runs a few questions through the research assistant, then prints the
error-analysis report for the same traces file.
"""

from pathlib import Path

from tracker.analysis import analyze
from tracker.cli import _markdown_table
from tracker.llm_client import anthropic_client
from tracker.pipeline import run

QUESTIONS = [
    "What are the main agentic design patterns?",
    "How do agents use tools?",
    "What is reflection in an agent loop?",
]

TRACES_PATH = Path("traces/demo_traces.jsonl")


def main() -> None:
    client = anthropic_client()
    if TRACES_PATH.exists():
        TRACES_PATH.unlink()

    for question in QUESTIONS:
        print(f"\n>>> {question}")
        trace = run(question, client=client, traces_path=TRACES_PATH)
        status = "ok" if trace.overall_success else "failed"
        print(f"{status}  trace_id={trace.trace_id}  cost_usd={trace.total_cost_usd:.6f}")
        for span in trace.spans:
            mark = "ok" if span.success else "FAIL"
            print(f"  [{mark}] {span.component}  {span.latency_ms:.1f} ms")
        if trace.final_output:
            print(trace.final_output)

    print("\n=== report ===")
    print(_markdown_table(analyze(TRACES_PATH)))


if __name__ == "__main__":
    main()
