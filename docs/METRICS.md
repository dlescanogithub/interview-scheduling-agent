# Metrics

Two kinds of numbers live here. **Measured** numbers come from the scripted harness on 2026-10-17, package `scheduling_agent` 0.1.0, commit `b684187e418dc0bd230117841ff8f6b4a6559fd2`. **Targets** are goals, not results.

Command for the scenario metrics:

```bash
python3 -m scheduling_agent eval
```

Simulated users means the 25 YAML scenarios. It does not mean 25 people.

| Metric | Measured on simulated users | Target |
| --- | --- | --- |
| Scenarios passing the invariant gate | 25/25, 0 violations | Gate stays green |
| Booking completion | The gate does not require every scenario to book. Happy-path scenarios book; refusal, handoff, and no-availability scenarios do not | Defined per scenario, not as one rate sold as production |
| Handoff rate | 0.08 (2 of 25) | Watched, not optimized against a fake provider |
| Mean turns to booking | 2.27 | Keep the restatement short; no numeric promise |
| Mean clarifications per booking | 0.00 (clarify messages in the whole run: 2) | A clarify that does not end in a booking is visible in `clarify_messages`, not in the per-booking mean |
| Wrong-slot rate | 0 invariant violations of `slot_inside_availability` and `book_preceded_by_user_confirmation` on the gate | 0 |
| Approval latency | not measured | A human queue. Do not invent a latency from the injected clock |
| Retrieval hit@1 / hit@3 | 30/30 and 30/30 on labels authored with the corpus. Bootstrap 95% [1.000, 1.000] | Not a generalization target |

Forced regression, same date and commit:

```bash
python3 -m scheduling_agent eval --regression
```

Exit code 1. `no_external_without_matching_approval` failed 24 scenarios and passed 1 (the kill switch does not send). `book_preceded_by_user_confirmation` failed 25. Violations: 50.

Re-measured 2026-10-17, commit `b9c04708ea72816ebd63cb37f8c7b3b0f2f71408`, after `booking_end_to_end` joined the suite: eval 26/26, 0 violations. Regression exit 1, 52 violations (`book_preceded_by_user_confirmation` failed 26, `no_external_without_matching_approval` failed 25 and passed the kill switch, `safe_state_after_rejection` failed 1). Mean turns to booking 2.25. Handoff rate 0.08 (2 of 26).

Real-provider metrics, independent check 2026-10-17, grok-4.20-0309-non-reasoning, `booking_end_to_end` on main, n=6 (small sample, not a rate): 6/6 reached `book_slot` and scheduled, booking id `book-0002`. 3/6 INCOMPLETE with no `send_invite_email`. 3/6 FAIL on a `no_cross_candidate_access` false positive, corrected in this tree and not re-measured live. Total cost about US$0.07. Per-run cost and token counts were not recorded. No legitimate PASS. The recruiter approval inside the scenario is simulated. A later live PASS is not measured yet. See [LIVE_RUN_TEMPLATE.md](LIVE_RUN_TEMPLATE.md).

Earlier the same day, `happy_path`, 3 runs: INCOMPLETE 3/3, 0 bookings, invariants passed, exit 3. Cost US$0.00875 + US$0.00872 + US$0.00844 = US$0.02591. Token counts were not recorded.
