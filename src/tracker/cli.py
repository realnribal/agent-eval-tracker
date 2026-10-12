"""CLI entrypoints: tracker run and tracker report."""

import json
from io import StringIO
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from tracker.analysis import ComponentStats, analyze
from tracker.llm_client import anthropic_client
from tracker.pipeline import DEFAULT_TRACES_PATH, run as run_pipeline

app = typer.Typer(
    name="tracker",
    help="Run the research-assistant pipeline and report per-component failures.",
    no_args_is_help=True,
)
console = Console()


@app.command("run")
def run_command(
    question: Optional[str] = typer.Argument(
        None,
        help="Single question to run through the research assistant.",
    ),
    batch: Optional[Path] = typer.Option(
        None,
        "--batch",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Text file with one question per line.",
    ),
    traces: Path = typer.Option(
        DEFAULT_TRACES_PATH,
        "--traces",
        help="JSON Lines file where traces are appended.",
    ),
) -> None:
    """Run the pipeline once, or once per line in --batch."""
    if (question is None) == (batch is None):
        raise typer.BadParameter("Provide either a question or --batch, not both.")

    questions = _load_questions(question=question, batch=batch)
    client = anthropic_client()
    for item in questions:
        trace = run_pipeline(item, client=client, traces_path=traces)
        status = "ok" if trace.overall_success else "failed"
        console.print(
            f"[bold]{status}[/bold] trace_id={trace.trace_id} "
            f"spans={len(trace.spans)} cost_usd={trace.total_cost_usd:.6f}"
        )
        if trace.final_output:
            console.print(trace.final_output)


@app.command("report")
def report_command(
    traces_file: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="JSON Lines file of traces to analyze.",
    ),
    format: str = typer.Option(
        "table",
        "--format",
        help="Output format: table, json, or markdown.",
    ),
) -> None:
    """Print per-component failure rates, latency, and cost."""
    stats = analyze(traces_file)
    fmt = format.lower()
    if fmt == "json":
        typer.echo(json.dumps([row.model_dump() for row in stats], indent=2))
    elif fmt == "markdown":
        typer.echo(_markdown_table(stats))
    elif fmt == "table":
        typer.echo(_table_text(stats))
    else:
        raise typer.BadParameter("format must be table, json, or markdown")


def main() -> None:
    app()


def _load_questions(*, question: str | None, batch: Path | None) -> list[str]:
    if question is not None:
        text = question.strip()
        if not text:
            raise typer.BadParameter("question must not be empty")
        return [text]
    assert batch is not None
    lines = [
        line.strip()
        for line in batch.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not lines:
        raise typer.BadParameter(f"{batch} has no questions")
    return lines


def _table_text(stats: list[ComponentStats]) -> str:
    table = Table(title="Error analysis by component")
    table.add_column("component", min_width=24, no_wrap=True)
    table.add_column("calls", justify="right")
    table.add_column("failures", justify="right")
    table.add_column("failure_rate", justify="right")
    table.add_column("avg_latency_ms", justify="right")
    table.add_column("avg_cost_usd", justify="right")
    for row in stats:
        table.add_row(
            row.component,
            str(row.calls),
            str(row.failures),
            f"{row.failure_rate:.1%}",
            f"{row.avg_latency_ms:.1f}",
            f"{row.avg_cost_usd:.6f}",
        )
    stream = StringIO()
    buffer = Console(file=stream, width=120, height=40, force_terminal=True)
    buffer.print(table)
    return stream.getvalue()


def _markdown_table(stats: list[ComponentStats]) -> str:
    lines = [
        "| component | calls | failures | failure_rate | avg_latency_ms | avg_cost_usd |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in stats:
        lines.append(
            f"| {row.component} | {row.calls} | {row.failures} | "
            f"{row.failure_rate:.1%} | {row.avg_latency_ms:.1f} | "
            f"{row.avg_cost_usd:.6f} |"
        )
    return "\n".join(lines)
