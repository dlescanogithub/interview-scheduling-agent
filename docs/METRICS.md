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

Real-provider metrics: none yet. Use [LIVE_RUN_TEMPLATE.md](LIVE_RUN_TEMPLATE.md) when a run exists.
