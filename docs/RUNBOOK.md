# Runbook

This lab has no production traffic. The steps below are the ones an operator would follow if the same gates were pointed at a real outbox later. Owners are roles, not named employers.

## Operate

- Install with `python3 -m pip install -e ".[dev]"`.
- Demo and eval use the scripted provider. Leave `LIVE_LLM` unset.
- To stop every external tool, set `EXTERNAL_TOOLS_ENABLED=0` and restart the process. The kill switch wins over the regression bypass.
- Live mode, if someone turns it on later, needs `LIVE_LLM=1`, a base URL, a key, a model, and `MAX_LIVE_SPEND_USD` greater than 0. The ledger path is `var/live-evals/ledger.jsonl` (git-ignored).

## Monitor

- The eval gate exit code. A non-zero gate means an invariant failed.
- JSON logs: `ts`, `level`, `msg`, `run_id`. A handoff is a warning with a reason (`provider_unavailable`, `cost_cap`, `tool_budget`, `max_turns`).
- Outbox length on a demo run. A row existing means an external tool passed the approval gate. It still did not leave the process.
- For a future live run: ledger `cost_status`, spend against the cap. The key must not appear in the file.

## Incidents

### Wrong invite

1. **Detect.** A person reports the slot, or an outbox row's start time does not match the confirmation in the trace.
2. **Contain.** Set `EXTERNAL_TOOLS_ENABLED=0`. Do not approve any further send. If the booking is only in the mock, cancel it from the session after the candidate confirms the cancel.
3. **Recover.** Tell the candidate the slot is not confirmed. A correction notice is another external tool and needs its own approval of those exact arguments. Do not reuse the previous approval hash.

Owner: the recruiter for what the candidate is told; the operator for the kill switch.

### Double booking

1. **Detect.** The invariant `no_double_booking` or `slot_inside_availability` fails, or two active rows overlap on the snapshot.
2. **Contain.** Stop new holds for that interviewer. The calendar method `book` already rejects a taken slot; a failure here means something wrote around it.
3. **Recover.** Cancel the later row with the candidate's confirmation, then book a free slot through the normal gates.

Owner: operator.

### Hold expired or slot stolen

1. **Detect.** Tool status `HOLD_EXPIRED` or `SLOT_TAKEN`.
2. **Contain.** Do not send an invite for that hold.
3. **Recover.** List availability again and restate a new slot. The previous yes does not apply.

Owner: the session (the agent loop) and the recruiter if an invite was already approved for the old slot.

### Provider keeps failing

1. **Detect.** Log reason `provider_unavailable` after the retry budget.
2. **Contain.** The loop hands off. No further external call is made in that handoff message.
3. **Recover.** A person finishes the booking. Rollback is "do nothing external", which is already the state.

Owner: operator for the provider; recruiter for the candidate.

### Live spend

1. **Detect.** `SpendCapError` or ledger cost above the cap. This is not retried.
2. **Contain.** The process stops calling. Do not raise the cap to finish a conversation in the same breath.
3. **Recover.** Read the ledger. Decide in a separate step whether a new cap is acceptable. Cost status `unknown` means prices were not set and only the token cap applied.

Owner: operator.

## Rollback

On the mock, rollback is `cancel_booking` after a cancel confirmation, then a cancellation notice only if a recruiter approves that call. There is no deployed service to roll back. Do not tag or ship this repo as a release from the lab alone.

## Handoff

The candidate can ask for a person. The scripted policy also hands off when retries, the cost cap, or the turn cap are exhausted. The handoff text says a person on the Taller Aurora team will continue, and that no further external action was taken.
