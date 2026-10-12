"""Per-component aggregates from a fixture traces.jsonl with known failures."""

from pathlib import Path

import pytest

from tracker.analysis import analyze

FIXTURE = Path(__file__).parent / "fixtures" / "sample_traces.jsonl"


def test_analyze_fixture_failure_rates_and_averages() -> None:
    by_name = {row.component: row for row in analyze(FIXTURE)}

    assert set(by_name) == {
        "generate_search_terms",
        "retrieve",
        "synthesize_answer",
    }

    terms = by_name["generate_search_terms"]
    assert terms.calls == 3
    assert terms.failures == 1
    assert terms.failure_rate == pytest.approx(1 / 3)
    assert terms.avg_latency_ms == pytest.approx((100.0 + 50.0 + 150.0) / 3)
    assert terms.avg_cost_usd == pytest.approx((0.0004 + 0.0 + 0.0002) / 3)

    retrieve = by_name["retrieve"]
    assert retrieve.calls == 3
    assert retrieve.failures == 0
    assert retrieve.failure_rate == pytest.approx(0.0)
    assert retrieve.avg_latency_ms == pytest.approx((10.0 + 10.0 + 20.0) / 3)
    assert retrieve.avg_cost_usd == pytest.approx(0.0)

    synth = by_name["synthesize_answer"]
    assert synth.calls == 3
    assert synth.failures == 2
    assert synth.failure_rate == pytest.approx(2 / 3)
    assert synth.avg_latency_ms == pytest.approx((200.0 + 100.0 + 200.0) / 3)
    assert synth.avg_cost_usd == pytest.approx((0.0008 + 0.0 + 0.0006) / 3)


def test_analyze_returns_components_sorted(tmp_path: Path) -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    path = tmp_path / "traces.jsonl"
    path.write_text(source, encoding="utf-8")

    names = [row.component for row in analyze(path)]

    assert names == sorted(names)


def test_analyze_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")

    assert analyze(path) == []
