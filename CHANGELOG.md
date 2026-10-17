# Changelog

## Unreleased

- After a recruiter approves, the runtime executes that stored call with the same `param_hash`. A different hash, a rejection, or no approval does not send. A second call with the same approval does not queue another outbox row.
- `no_send_claim_without_outbox` fails when the assistant says the invite was sent or the approval was already consumed and no external send executed. The live command prints `expect_failures`.
- `no_cross_candidate_access` still misses an obfuscated address, an address with spaces, and a first name alone.
- `booking_end_to_end` now asks "Sí, enviá el email." before the recruiter step. That recruiter step is a simulated approval inside the scenario. PASS still needs the booking, the invite in the outbox, the approval, and clean invariants.
- `no_cross_candidate_access` compares names, addresses, and ids before redaction. The placeholder `[email]` is not treated as another candidate. Naming another candidate's address or id still fails the check.
- `booking_end_to_end` adds the second explicit yes and the recruiter approval so a live run can finish a booking. `happy_path` stays the two-turn cutoff and is INCOMPLETE without `book_slot`.
- A short confirmation accepts the pending numbered slot, and that slot is passed back to the model as `pending_slot`.
- Assistant text that shows a clock time without a zone and an offset is rewritten before the user sees it.
- Tool argument errors, including a naive datetime or an unknown interviewer id, return a structured tool result instead of crashing the process.
- The live command prints `INCOMPLETE` when the invariants hold but the scenario did not finish a booking. PASS requires both.

## 0.1.0

- Mock calendar, tool registry, two confirmation gates, scripted agent loop, local FAQ retrieval, scenario invariant gate, and an optional capped live adapter.
- All fixtures are synthetic. No live-provider run is included.
