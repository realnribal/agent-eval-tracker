"""Latency, token cost, and exception capture for the LLM client. The API is mocked."""

from types import SimpleNamespace

import pytest

from tracker.llm_client import PRICING_USD_PER_MTOK, call


class _Clock:
    def __init__(self, times: list[float]) -> None:
        self._times = iter(times)

    def __call__(self) -> float:
        return next(self._times)


class _Messages:
    def __init__(self, *, response: object | None = None, error: BaseException | None = None) -> None:
        self._response = response
        self._error = error
        self.kwargs: dict[str, object] | None = None

    def create(self, **kwargs: object) -> object:
        self.kwargs = kwargs
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


class _Client:
    def __init__(self, messages: _Messages) -> None:
        self.messages = messages


def _response(text: str, *, input_tokens: int, output_tokens: int) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def test_successful_call_fills_latency_tokens_and_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tracker.llm_client.time.perf_counter", _Clock([10.0, 10.25]))
    messages = _Messages(response=_response("reflection, then tool use", input_tokens=1_000, output_tokens=500))
    model = "claude-sonnet-4-6"
    rates = PRICING_USD_PER_MTOK[model]

    span = call(
        _Client(messages),
        component="generate_search_terms",
        prompt="What are the main agentic design patterns?",
        model=model,
        max_tokens=256,
    )

    assert span.success is True
    assert span.error is None
    assert span.component == "generate_search_terms"
    assert span.input == "What are the main agentic design patterns?"
    assert span.output == "reflection, then tool use"
    assert span.latency_ms == pytest.approx(250.0)
    assert span.input_tokens == 1_000
    assert span.output_tokens == 500
    assert span.cost_usd == pytest.approx(
        (1_000 * rates["input_per_mtok"] + 500 * rates["output_per_mtok"]) / 1_000_000
    )
    assert messages.kwargs == {
        "model": model,
        "max_tokens": 256,
        "messages": [{"role": "user", "content": "What are the main agentic design patterns?"}],
    }


def test_exception_returns_a_failed_span(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("tracker.llm_client.time.perf_counter", _Clock([1.0, 1.04]))
    messages = _Messages(error=RuntimeError("overloaded"))

    span = call(
        _Client(messages),
        component="synthesize_answer",
        prompt="hello",
        model="claude-sonnet-4-6",
        max_tokens=32,
    )

    assert span.success is False
    assert span.error == "overloaded"
    assert span.output is None
    assert span.input_tokens is None
    assert span.output_tokens is None
    assert span.cost_usd is None
    assert span.latency_ms == pytest.approx(40.0)


def test_anthropic_client_reads_only_the_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    class _FakeAnthropic:
        def __init__(self, *, api_key: str) -> None:
            captured["api_key"] = api_key

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("tracker.llm_client.Anthropic", _FakeAnthropic)

    from tracker.llm_client import anthropic_client

    anthropic_client()

    assert captured == {"api_key": "test-key"}
