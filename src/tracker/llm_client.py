"""Anthropic call wrapper that returns a Span."""

import os
import time
from datetime import datetime, timezone
from typing import Protocol

from anthropic import Anthropic

from tracker.trace import Span

PRICING_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input_per_mtok": 3.0, "output_per_mtok": 15.0},
}


class SupportsMessages(Protocol):
    """Any client that exposes ``messages.create``, so the provider can be swapped later."""

    messages: object


def anthropic_client() -> Anthropic:
    """Build an Anthropic client from the ``ANTHROPIC_API_KEY`` environment variable."""
    return Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def call(
    client: SupportsMessages,
    *,
    component: str,
    prompt: str,
    model: str,
    max_tokens: int,
) -> Span:
    """Call ``client.messages.create`` and return one Span. Exceptions stay inside the Span."""
    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        latency_ms = (time.perf_counter() - started) * 1000
        ended_at = datetime.now(timezone.utc)
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        return Span(
            component=component,
            input=prompt,
            output=_output_text(response),
            started_at=started_at,
            ended_at=ended_at,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=_cost_usd(model, input_tokens, output_tokens),
            success=True,
            error=None,
        )
    except Exception as exc:
        return Span(
            component=component,
            input=prompt,
            output=None,
            started_at=started_at,
            ended_at=datetime.now(timezone.utc),
            latency_ms=(time.perf_counter() - started) * 1000,
            input_tokens=None,
            output_tokens=None,
            cost_usd=None,
            success=False,
            error=str(exc),
        )


def _cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = PRICING_USD_PER_MTOK[model]
    return (
        input_tokens * rates["input_per_mtok"] + output_tokens * rates["output_per_mtok"]
    ) / 1_000_000


def _output_text(response: object) -> str:
    parts: list[str] = []
    for block in response.content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)
