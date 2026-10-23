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

Re-measured 2026-10-17, commit `87eb459a88846f58b85cf0f93520afb1fbae4d52`: `python3 -m pytest` 108 passed, coverage 91.07%. Eval still 26/26, 0 violations. Regression still exit 1, 52 violations. `no_cross_candidate_access` stayed 26 pass / 0 fail on that regression.

Re-measured 2026-10-17, commit `afc5f6d96fe99e70bb5d677e3d2b75e5489b5550`, Python 3.12.3. `python3 -m pytest`: 114 passed, coverage 90.60%. `python3 -m scheduling_agent eval`: 26/26, 12 invariants, 0 violations. `python3 -m scheduling_agent eval --regression`: exit 1, 54 violations (`no_send_claim_without_outbox` failed `kill_switch` twice; 25 approval, 26 confirmation, 1 safe-state). Mean turns to booking 2.25. Handoff rate 0.08 (2 of 26).

Re-measured 2026-10-17, commit `9b11c77fea78a8ee2d31864a0fb6e729e1ee8453`, Python 3.12.3. `python3 -m pytest`: 116 passed, coverage 90.68%. Eval still 26/26, 0 violations. Regression still exit 1, 54 violations.

Re-measured 2026-10-17, commit `ab4e24617f1250074ffe998892c0267d5f179aa3`, Python 3.12.3, with `LIVE_LLM=1` exported and a non-routable base URL. `python3 -m pytest`: 124 passed, coverage 90.79%. Eval still 26/26, 0 violations. Regression still exit 1, 54 violations. The suite did not open a socket.

Re-measured 2026-10-17, commit `cc5c233ea771e218f4bb2f28c2df503889db0917`, Python 3.12.3, with `LIVE_LLM=1` exported and a non-routable base URL. `python3 -m pytest`: 122 passed, coverage 90.79%. Eval still 26/26, 0 violations. Regression still exit 1, 54 violations. The suite did not open a socket.

Re-measured 2026-10-17, commit `a9b21e5388fafdaaf0b4fa3dd5f5c440ecaf9948`, Python 3.12.3, with `LIVE_LLM=1` exported and a non-routable base URL. `python3 -m pytest`: 120 passed, coverage 90.77%. Eval still 26/26, 0 violations. Regression still exit 1, 54 violations. The suite did not open a socket.

Re-measured 2026-10-17, commit `bcfd136d8dbbbcdcb9597e96601eee8563c7d620`, Python 3.12.3, with `LIVE_LLM=1` exported and a non-routable base URL. `python3 -m pytest`: 118 passed, coverage 90.65%. Eval still 26/26, 0 violations. Regression still exit 1, 54 violations. The suite did not open a socket. External verification of that same HEAD (VERIFY_REPORT_9, Python 3.12.15) also got 118 passed, 90.65%, and 0 calls to api.x.ai with `LIVE_LLM=1` and a fake key. The previous commit `4d512df` with that environment failed 2 tests and made 6 calls to api.x.ai.

Re-measured 2026-10-22, code revision `25ad14d`, Python 3.12.3, pytest 9.1.1, package 0.1.0. `python3 -m pytest`: 124 passed. Statement (line) coverage 93.95% (2780 of 2959 statements; `percent_statements_covered` 93.95065900642109). The pytest-cov total on that run, which includes branches because branch coverage is enabled, is 90.79% (printed `Total coverage: 90.79%`). That combined figure matches the 2026-10-17 line for 124 passed. It is not a coverage increase. The run printed `CoverageWarning: Module scheduling_agent was previously imported, but not measured`. `python3 -m scheduling_agent eval`: 26/26, 0 violations. `python3 -m scheduling_agent eval --regression`: exit 1, 54 violations (25 approval, 2 send-claim lines on `kill_switch`, 26 confirmation, 1 safe-state). Simulated users: mean turns to booking 2.25, mean clarifications per booking 0.00, clarify messages 2, handoff rate 0.08 (2 of 26). Retrieval hit@1 30/30, hit@3 30/30, bootstrap 95% [1.000, 1.000], labels authored with the corpus. That retrieval row is previous data on the bilingual corpus. Live mode was not run.

Re-measured 2026-10-23, code revision `0204f8b`, Python 3.12.3, pytest 9.1.1, package `scheduling_agent` 0.1.1. `python3 -m pytest`: 125 passed. Statement coverage 94.12% (2754 of 2926; `percent_statements_covered` 94.12166780587833). pytest-cov total 91.02% (printed `Total coverage: 91.02%`; `percent_covered` 91.01601601601601). Branch coverage 82.52% (883 of 1070; 157 partial; `percent_branches_covered` 82.5233644859813). Eval 26/26, 0 violations. Regression exit 1, 54 violations (26 confirmation, 25 approval, 2 send-claim lines on `kill_switch`, 1 safe-state). Simulated users: mean turns to booking 2.25, mean clarifications per booking 0.00, clarify messages 2, handoff rate 0.08 (2 of 26). Retrieval on the English labels written with the English corpus: hit@1 30/30, hit@3 30/30, bootstrap 95% [1.000, 1.000]. ruff, the format check, and mypy (25 source files) passed. Secret scan: no findings. Live mode was not run. Live mode on this revision is UNVERIFIED.

Real-provider metrics, independent check 2026-10-17, grok-4.20-0309-non-reasoning, `booking_end_to_end` on main after the approved-send change, one model, small sample, not a rate. First sample n=5: 5/5 PASS with a simulated approval (outbox=1, origin=approval, same param_hash), about US$0.11. Three more runs: PASS 3/3, US$0.054. Together that was 8/8 PASS with a simulated approval. External verification the same day (VERIFY_REPORT_9, HEAD `4c2170d`, cost = `usage.cost_in_usd_ticks`) added PASS 3/3: US$0.02512, US$0.02060 and US$0.02156, sum US$0.06728 (28 calls, 0 errors; 30–36k tokens in, 612–779 out per run; hash `f69ebd9b`, origin approval, outbox `out-0004`). That was 11/11 PASS with a simulated approval (those 8 plus these 3). External verification of the verb expansion (VERIFY_REPORT_10, HEAD `bb314c9`, Python 3.12.15, cost = `usage.cost_in_usd_ticks`) added PASS 3/3: US$0.01766, US$0.02300 and US$0.01312, sum US$0.05378 (27 calls, 0 errors; about 31k tokens in, 625–714 out per run; hash `f69ebd9b`, origin approval, outbox `out-0004`). That was 14/14 PASS with a simulated approval (those 11 plus these 3). External verification of the word-boundary detector (VERIFY_REPORT_11, HEAD `c525227`, Python 3.12.15, cost = `usage.cost_in_usd_ticks`) added 1 PASS: US$0.0205215, 10 calls, 35629 tokens in (24576 cached), 716 out, hash `f69ebd9b`, origin approval, outbox `out-0004`. Cumulative 15/15 PASS with a simulated approval (those 14 plus this 1), n=15. That does not prove the model retries the tool: the runtime executes the approved call. Four other runs were INCOMPLETE on the verifier's caps (US$0.028 ×3 = US$0.0347365, 18 calls; US$0.035 ×1 = US$0.0116923, 7 calls), `cost_cap` before the send, invariants passed, outbox=0. Not PASS and not FAIL. Per-run splits and token counts for the earlier 8 were not recorded. Each report's combined spend includes other repos. This repo's slice of VERIFY_REPORT_9 is US$0.06728, of VERIFY_REPORT_10 is US$0.05378 (that report's total is US$0.06837), and of VERIFY_REPORT_11 is US$0.0205215 plus US$0.0464288 on the aborted caps (that report's total is about US$0.0770). An offline adversarial check the same day found no bypass of the human gate in 11 cases. See [LIVE_RUN_TEMPLATE.md](LIVE_RUN_TEMPLATE.md).

On that PASS the ledger's full input price (cached tokens billed at US$1.25/M) estimates about US$0.046. Ticks were US$0.0205215, about 2.3× lower, because 24576 of the prompt tokens were cached (US$0.20/M in the verifier's price note). `LLM_PRICE_CACHED_PER_MTOK` discounts the settled row. The reservation before the call still uses the full input price and `estimate × 2`, so a cap under about US$0.06 can abort a run the tick cost would have allowed. The PASS used a cap of US$0.06. Overestimating is conservative.

`no_send_claim_without_outbox` on a new set, empty outbox, measured on the previous Spanish wording before "none" and "nothing" counted as negation (VERIFY_REPORT_11, HEAD `c525227`, n=20, small, not conclusive, about ±15 points): recall 18/20, false positives 1/20. After a real send, 0/20 of that set were flagged. The same report's re-score of the VERIFY_REPORT_10 list was 20/20 and 0/20 false positives, and it is not independent: the tests use those literals. VERIFY_REPORT_10's own 15/20 was a different list. Those rates do not measure the English detector. No new n=20 recall was run on 2026-10-23. External verification of HEAD `c525227` (VERIFY_REPORT_11, Python 3.12.15) also got 122 passed, 90.79%, and 0 calls to api.x.ai with `LIVE_LLM=1` and a fake key. External verification of HEAD `bb314c9` (VERIFY_REPORT_10) got 120 passed, 90.77%, and 0 calls to api.x.ai.

Earlier the same day, n=8 on main before that runtime change: 0/8 PASS, 8/8 INCOMPLETE, 0 FAIL, 0 `no_cross_candidate_access` false positives, outbox=0. Round-set cost about US$0.15.

Earlier the same day, n=6 on the same scenario: 6/6 booked, 3/6 INCOMPLETE with no `send_invite_email`, 3/6 FAIL on the cross-candidate false positive. Total cost about US$0.07.

Earlier the same day, `happy_path`, 3 runs: INCOMPLETE 3/3, 0 bookings, invariants passed, exit 3. Cost US$0.00875 + US$0.00872 + US$0.00844 = US$0.02591. Token counts were not recorded.
