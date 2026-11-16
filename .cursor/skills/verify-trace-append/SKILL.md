---
name: verify-trace-append
description: "Check that append_trace writes one whole JSONL trace line, including when two runs append to the same file. Use when editing src/tracker/trace.py, append_trace, read_traces, trace_to_jsonl, or the traces JSONL format."
---

# Verify that append_trace keeps whole JSONL records

`append_trace` in `src/tracker/trace.py` must write one complete JSON Lines record per trace. `read_traces` must then return each of those traces once. Two `tracker run` processes can share `traces/traces.jsonl`. If a line tears, `tracker report` raises, and the failure rates the user acts on are incomplete.

After any two `append_trace` calls, overlapping or not, `read_traces` returns both traces, each on its own line. A torn line either crashes `tracker report` or drops a run.

## What the check covers

| Check | Code | One step |
| --- | --- | --- |
| `RecordsStayWhole` | `append_trace`, `trace_to_jsonl`, and `read_traces` in `src/tracker/trace.py` | one `handle.write` call |

`trace_to_jsonl` is `Trace.model_dump_json()`. That value is the body write. The newline is a second write. `read_traces` is the parser that decides whether the property held.

Last confirmed that the model and the checker describe that code at commit `2694d9b216871fcbf37270b6fdd13dd31c7b518d`. Move this commit forward only after you read the diff of those three functions and confirm that the verification still describes them. A pass against a stale description is not a pass. If those functions changed and you have not confirmed the description, stop. Update the model or the checker first. Use `/maintain-formal-verification-skill` when the change landed without this skill.

## Bounds and assumptions

- Two writers. Each does the writes that `append_trace` actually performs.
- One `handle.write` is atomic. The checker does not split a single write into bytes.
- The JSON body contains no newline. `model_dump_json` emits one line today.
- Not covered: a crash mid-write, a full disk, three or more overlapping appends, `pipeline.run` choosing when to call `append_trace`, and the numbers in `analyze_traces`.

## Run the checker

From the repo root:

```bash
uv run python .cursor/skills/verify-trace-append/check_append.py
```

Exit 0 means every interleaving of the real writes parses as both traces. Exit 1 means it does not, or the writes no longer match the TLA+ model.

Read a TLC result with `/statechart`. Do not copy its command into this skill. The spec is `.cursor/skills/verify-trace-append/TraceAppend.tla`. The view is `view.mjs` beside it. Give `/statechart` a new empty `--out` folder each run.

## Read the checker output

- `single_writer` PASS means one append, alone, is one trace.
- `ordered_append` PASS means one append that finishes before the other still yields two traces.
- `every_interleaving` FAIL means some overlap tears a line. On the sync commit, that FAIL is the finding, not a broken checker.
- `tla_model_matches_writes` is false when an append is no longer exactly a JSON body write and then a newline write. TLC then describes an old shape. Update `TraceAppend.tla` from the code before you trust it. Do not drop a write from the model only to make `RecordsStayWhole` pass.

A `ValidationError` from `read_traces` on a torn interleaving means the property failed. A checker crash before it prints `every_interleaving` means the checker is broken, not the product.

## Known finding

On the sync commit, `single_writer` and `ordered_append` pass, and `every_interleaving` fails. The short tear is: run A writes its JSON, run B writes its JSON, run B writes the newline, run A writes the newline. `read_traces` then sees one line with two JSON values. The code does those as two separate `handle.write` calls, so the overlap is a real schedule. Do not weaken `RecordsStayWhole` or skip that interleaving.

## When the code changes on purpose

If a change makes one `write` of the JSON plus the newline, the checker should exit 0. TLC's `RecordsStayWhole` should hold after you collapse `WriteBody` and `WriteNewline` into that one write. Update the model from the new code, rerun both, then move the sync commit.

If a change adds a write, keep it as its own step. Rerun. A new failure is a finding until the author of the change says the promise itself changed.
