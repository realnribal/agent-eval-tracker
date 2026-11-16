"""Check append_trace against overlapping writes, using the real function.

One handle.write is one step. append_trace does two: the JSON body, then a newline.
This enumerates every interleaving of those steps for two traces and parses the
result with read_traces.
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from tracker.trace import Span, Trace, append_trace, read_traces


def _trace(trace_id: str) -> Trace:
    now = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)
    span = Span(
        component="retrieve",
        input={"queries": [trace_id]},
        output={"snippets": [trace_id]},
        started_at=now,
        ended_at=now,
        latency_ms=1.0,
        input_tokens=None,
        output_tokens=None,
        cost_usd=None,
        success=True,
        error=None,
    )
    return Trace(
        trace_id=trace_id,
        pipeline_name="research_assistant",
        input={"question": trace_id},
        final_output=trace_id,
        spans=[span],
        started_at=now,
        ended_at=now,
        total_latency_ms=1.0,
        total_cost_usd=0.0,
        overall_success=True,
    )


def _capture(trace: Trace) -> list[str]:
    chunks: list[str] = []

    class _Handle:
        def write(self, data: str) -> int:
            chunks.append(data)
            return len(data)

        def __enter__(self) -> _Handle:
            return self

        def __exit__(self, *args: object) -> bool:
            return False

    def _open(self: Path, mode: str = "r", *args: object, **kwargs: object) -> _Handle:
        return _Handle()

    with patch.object(Path, "open", _open):
        append_trace("traces/traces.jsonl", trace)
    return chunks


def _schedules(n_a: int, n_b: int) -> list[list[tuple[str, int]]]:
    def rec(i_a: int, i_b: int) -> list[list[tuple[str, int]]]:
        if i_a == n_a and i_b == n_b:
            return [[]]
        out: list[list[tuple[str, int]]] = []
        if i_a < n_a:
            for rest in rec(i_a + 1, i_b):
                out.append([("A", i_a), *rest])
        if i_b < n_b:
            for rest in rec(i_a, i_b + 1):
                out.append([("B", i_b), *rest])
        return out

    return rec(0, 0)


def _parse(text: str) -> list[Trace]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "traces.jsonl"
        path.write_text(text, encoding="utf-8")
        return read_traces(path)


def _ids(traces: list[Trace]) -> list[str]:
    return [trace.trace_id for trace in traces]


def _text(chunks_a: list[str], chunks_b: list[str], order: list[tuple[str, int]]) -> str:
    chunks = {"A": chunks_a, "B": chunks_b}
    return "".join(chunks[writer][index] for writer, index in order)


def _step_names(chunks_a: list[str], chunks_b: list[str], order: list[tuple[str, int]]) -> str:
    chunks = {"A": chunks_a, "B": chunks_b}
    who = {"A": "run A", "B": "run B"}
    return ", ".join(
        f"{who[writer]} {_kind(chunks[writer][index])}" for writer, index in order
    )


def _kind(chunk: str) -> str:
    return "writes the newline" if chunk == "\n" else "writes its JSON"


def main() -> int:
    run_a = _trace("run_a")
    run_b = _trace("run_b")
    chunks_a = _capture(run_a)
    chunks_b = _capture(run_b)

    print(f"writes_per_append_a: {len(chunks_a)}")
    print(f"writes_per_append_b: {len(chunks_b)}")
    body_has_newline = any("\n" in chunk and chunk != "\n" for chunk in chunks_a + chunks_b)
    print(f"json_body_contains_newline: {body_has_newline}")

    single_ok = True
    for name, chunks, trace in (("run A", chunks_a, run_a), ("run B", chunks_b, run_b)):
        try:
            got = _parse("".join(chunks))
        except Exception as exc:
            print(f"single_writer {name}: FAIL {type(exc).__name__}: {exc}")
            single_ok = False
            continue
        if _ids(got) != [trace.trace_id]:
            print(f"single_writer {name}: FAIL got {_ids(got)}")
            single_ok = False
        else:
            print(f"single_writer {name}: PASS")

    ordered_ok = True
    for label, text in (
        ("A then B", "".join(chunks_a + chunks_b)),
        ("B then A", "".join(chunks_b + chunks_a)),
    ):
        try:
            got = _parse(text)
        except Exception as exc:
            print(f"ordered_append {label}: FAIL {type(exc).__name__}: {exc}")
            ordered_ok = False
            continue
        if sorted(_ids(got)) != ["run_a", "run_b"]:
            print(f"ordered_append {label}: FAIL got {_ids(got)}")
            ordered_ok = False
        else:
            print(f"ordered_append {label}: PASS")

    bad: list[str] = []
    orders = _schedules(len(chunks_a), len(chunks_b))
    for order in orders:
        text = _text(chunks_a, chunks_b, order)
        label = _step_names(chunks_a, chunks_b, order)
        try:
            got = _parse(text)
        except Exception as exc:
            bad.append(f"{label} -> {type(exc).__name__}: {exc}")
            continue
        if sorted(_ids(got)) != ["run_a", "run_b"]:
            bad.append(f"{label} -> traces {_ids(got)}")

    print(f"interleavings: {len(orders)}")
    print(f"torn_interleavings: {len(bad)}")
    if bad:
        print("tear:")
        canonical = (
            "run A writes its JSON, run B writes its JSON, "
            "run B writes the newline, run A writes the newline"
        )
        print(next((item for item in bad if item.startswith(canonical)), bad[0]))
        print("every_interleaving: FAIL")
    else:
        print("every_interleaving: PASS")

    model_matches = (
        len(chunks_a) == 2
        and len(chunks_b) == 2
        and chunks_a[1] == "\n"
        and chunks_b[1] == "\n"
        and "\n" not in chunks_a[0]
        and "\n" not in chunks_b[0]
    )
    print(f"tla_model_matches_writes: {model_matches}")
    if not model_matches:
        print(
            "model_drift: TraceAppend.tla assumes each append is WriteBody then WriteNewline. "
            "The captured writes are different. Do not treat a TLC result as this code."
        )

    if body_has_newline or not single_ok or not ordered_ok or bad or not model_matches:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
