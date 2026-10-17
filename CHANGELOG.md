# Changelog

## Unreleased

- A short confirmation accepts the pending numbered slot, and that slot is passed back to the model as `pending_slot`.
- Assistant text that shows a clock time without a zone and an offset is rewritten before the user sees it.
- Tool argument errors, including a naive datetime or an unknown interviewer id, return a structured tool result instead of crashing the process.
- The live command prints `INCOMPLETE` when the invariants hold but the scenario did not finish a booking. PASS requires both.

## 0.1.0

- Mock calendar, tool registry, two confirmation gates, scripted agent loop, local FAQ retrieval, scenario invariant gate, and an optional capped live adapter.
- All fixtures are synthetic. No live-provider run is included.
