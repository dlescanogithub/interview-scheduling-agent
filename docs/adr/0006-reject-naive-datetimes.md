# ADR 0006: Reject naive datetimes

## Status

Accepted

## Context

A live model sent `2026-04-14T00:00:00` to `list_availability`. `parse_iso` raised `ValueError: naive datetime`, and nothing caught it, so the process crashed. Guessing that the value was UTC, or that it was Buenos Aires, would book the wrong instant whenever the model forgot the offset.

## Decision

Naive datetimes are rejected. They are not read as UTC and not read as `America/Argentina/Buenos_Aires`. The tool gateway catches `ValueError`, unknown ids, and invalid JSON and returns a tool result the model can read. The fix text for a missing offset is: `datetime debe incluir offset, ej. 2026-10-20T10:00:00-03:00`.

The live system prompt states the current instant in Buenos Aires, with a numeric offset, and the exact interviewer ids plus their working windows.

## Consequences

A bad call stays inside the conversation. The model can correct the offset or the id and try again. A run that never books is not reported as PASS: the live command prints `INCOMPLETE` and exits 3 when the invariants hold but the scenario's booking did not happen.
