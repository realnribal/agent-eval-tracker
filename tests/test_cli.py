"""CLI wiring for tracker run and tracker report."""

import json
from datetime import datetime, timezone
from pathlib import Path

from typer.testing import CliRunner

from tracker.cli import app
from tracker.trace import Span, Trace

runner = CliRunner()
FIXTURE = Path(__file__).parent / "fixtures" / "sample_traces.jsonl"


def _trace(*, overall_success: bool, final_output: str | None) -> Trace:
    now = datetime.now(timezone.utc)
    span = Span(
        component="synthesize_answer",
        input="q",
        output=final_output,
        started_at=now,
        ended_at=now,
        latency_ms=5.0,
        input_tokens=1,
        output_tokens=1,
        cost_usd=0.0001,
        success=overall_success,
        error=None if overall_success else "empty synthesis",
    )
    return Trace(
        trace_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        pipeline_name="research_assistant",
        input={"question": "q"},
        final_output=final_output,
        spans=[span],
        started_at=now,
        ended_at=now,
        total_latency_ms=5.0,
        total_cost_usd=0.0001,
        overall_success=overall_success,
    )


def test_report_table_shows_component_columns() -> None:
    result = runner.invoke(app, ["report", str(FIXTURE)])

    assert result.exit_code == 0
    assert "Error analysis by component" in result.stdout
    assert "generate_search_terms" in result.stdout
    assert "synthesize_answer" in result.stdout
    assert "failure_rate" in result.stdout
    assert "avg_latency_ms" in result.stdout
    assert "avg_cost_usd" in result.stdout


def test_report_json_format() -> None:
    result = runner.invoke(app, ["report", str(FIXTURE), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert {row["component"] for row in payload} == {
        "generate_search_terms",
        "retrieve",
        "synthesize_answer",
    }
    synth = next(row for row in payload if row["component"] == "synthesize_answer")
    assert synth["calls"] == 3
    assert synth["failures"] == 2


def test_report_markdown_format() -> None:
    result = runner.invoke(app, ["report", str(FIXTURE), "--format", "markdown"])

    assert result.exit_code == 0
    assert "| component |" in result.stdout
    assert "synthesize_answer" in result.stdout


def test_run_single_question_uses_pipeline(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    traces_path = tmp_path / "traces.jsonl"

    def fake_client():
        return object()

    def fake_run(question, *, client, traces_path):
        calls.append(question)
        return _trace(overall_success=True, final_output="patterns: reflection, tool use")

    monkeypatch.setattr("tracker.cli.anthropic_client", fake_client)
    monkeypatch.setattr("tracker.cli.run_pipeline", fake_run)

    result = runner.invoke(
        app,
        ["run", "What are the main agentic design patterns?", "--traces", str(traces_path)],
    )

    assert result.exit_code == 0
    assert calls == ["What are the main agentic design patterns?"]
    assert "ok" in result.stdout
    assert "patterns: reflection, tool use" in result.stdout


def test_run_batch_reads_one_question_per_line(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    batch = tmp_path / "questions.txt"
    batch.write_text("first question\n\nsecond question\n", encoding="utf-8")

    def fake_client():
        return object()

    def fake_run(question, *, client, traces_path):
        calls.append(question)
        return _trace(overall_success=False, final_output=None)

    monkeypatch.setattr("tracker.cli.anthropic_client", fake_client)
    monkeypatch.setattr("tracker.cli.run_pipeline", fake_run)

    result = runner.invoke(
        app,
        ["run", "--batch", str(batch), "--traces", str(tmp_path / "traces.jsonl")],
    )

    assert result.exit_code == 0
    assert calls == ["first question", "second question"]
    assert result.stdout.count("failed") == 2


def test_run_rejects_question_and_batch_together(tmp_path: Path) -> None:
    batch = tmp_path / "questions.txt"
    batch.write_text("only\n", encoding="utf-8")

    result = runner.invoke(app, ["run", "a question", "--batch", str(batch)])

    assert result.exit_code != 0
