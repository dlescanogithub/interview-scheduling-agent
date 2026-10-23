# How it works

This is a lab with invented data from Taller Aurora, a fictional co-op. The "brain" that runs in CI is a script, not a model. It shows the tools, the gates, and the rules. It does not show the quality of a model.

The same measured numbers are in the README. The hours model is in `docs/BUSINESS_VALUE.md`.

## What was measured on 2026-10-22

**MEASURED** on 2026-10-22, Python 3.12.3, pytest 9.1.1, package `scheduling_agent` 0.1.0, code revision `25ad14d` (a docs-only change does not touch the package). `python3 -m pytest`: 124 passed. Line coverage (statements): 93.95% (2780 of 2959). The total pytest-cov prints, which mixes lines and branches because branch coverage is on, is 90.79%. That 90.79% is the same combined number already published for 124 tests on 2026-10-17. It is not a coverage increase. `python3 -m scheduling_agent eval`: 26/26, 0 violations. `python3 -m scheduling_agent eval --regression`: exits 1 with 54 violations. Simulated users on that run: mean turns to booking 2.25, mean clarifications per booking 0.00, clarify messages 2, handoff rate 0.08 (2 of 26).

Live mode on this revision is **UNVERIFIED**. On 2026-10-22 no provider was called, and code revision `25ad14d` did not call one either. The sample below is from 2026-10-17, on earlier commits (through `c525227`), before `ningún` / `nada` counted as negation and before the cached price. It does not verify this tree.

## Analogy

Think of a front desk. The person writes the slot in pencil, reads it back in full (day, time, and zone), and only after you say yes does it go to the person who sends the email. If nobody approves, the email stays in an outbox that does not go anywhere.

## Step by step

1. You open a session with a candidate, their time zone, and a fixed clock. The clock is not the wall clock: tests move it forward when they want to see an expired hold.
2. The script asks for availability. The in-memory calendar returns at most 3 openings, with a duration of 45 minutes and a buffer of 15.
3. The text you see lists at most three numbered openings, with zone and offset, for example `1) mar 20/10 10:00 (ART, UTC-3)`. If a reply brings a time without a zone, it is not shown: it goes back to the model to be rewritten, with a bounded retry.
4. A "Sí, confirmo.", a "la 1", or an "ese" accepts the last opening offered. That opening is stored as `pending_slot` and the model sees it in the context, so it does not ask which one it was again. If you do not confirm, nothing is booked.
5. The invite email is an external tool. Without a recruiter approval bound to the hash of those arguments, it does not run. Approval of 10:00 does not cover 11:00. In this repo that approval is simulated. In production it has to arrive on an authenticated channel, and this repo does not implement that channel.
6. If the recruiter rejects, the action ends and the agent says what happens next. It does not retry the same send in secret.
7. At the end, a check reads the trace and asks whether the invariants held. It does not require the exact sequence of calls.

## Glossary

| Word | What it is |
| --- | --- |
| Hold | A temporary reservation. It expires if the injected clock moves past the TTL. |
| Outbox | An in-memory list of emails that "would be sent". There is no mail server. |
| Parameter hash | A hash of the tool and its arguments. The approval covers that hash, not "a similar email". |
| Invariant | A property of the trace. For example: two slots do not overlap. |
| Kill switch | `EXTERNAL_TOOLS_ENABLED=0`. With that off, no external tool runs, not even in regression mode. |
| Provider scripted | The deterministic script. It is not a model. |

Read the trace if something does not add up. Check that the email you are about to approve is the same opening the person confirmed. The kill switch is there if every send has to stop.

## Limits

- Live mode on this revision is **UNVERIFIED**. What follows is the **MEASURED** sample from 2026-10-17, on earlier commits, not on this tree.
- Independent verification on 2026-10-17, grok-4.20-0309-non-reasoning, `booking_end_to_end` on main after the approved-send fix, one model, small sample, not a rate. First sample n=5: 5/5 PASS with a simulated approval (outbox=1, origin=approval, same param_hash), about US$0.11. Three more runs the same day: PASS 3/3, US$0.054. Together that was 8/8. External verification the same day (VERIFY_REPORT_9, HEAD `4c2170d`, cost = `usage.cost_in_usd_ticks`) added 3 runs: PASS 3/3, US$0.02512 + US$0.02060 + US$0.02156 = US$0.06728 (28 calls, 0 errors). That was 11/11. External verification of the verb expansion (VERIFY_REPORT_10, HEAD `bb314c9`, cost = `usage.cost_in_usd_ticks`) added 3 runs: PASS 3/3, US$0.01766 + US$0.02300 + US$0.01312 = US$0.05378 (27 calls, 0 errors). That was 14/14. External verification of the detector with `\bno\b` (VERIFY_REPORT_11, HEAD `c525227`, cost = `usage.cost_in_usd_ticks`) added 1 PASS: US$0.0205215, 10 calls, 35629 tokens in (24576 cached), 716 out. Cumulative 15/15 PASS with a simulated approval (those 14 plus this 1), n=15. That report's combined spend is about US$0.0770 and includes other repos. Four more runs were INCOMPLETE because of the verifier's cap (US$0.028 ×3 and US$0.035 ×1). They are not PASS and not FAIL. That does not prove the model retries the tool: the runtime executes the approved call. The ledger, without `LLM_PRICE_CACHED_PER_MTOK`, bills cached tokens at the full input price: on that PASS it estimates about US$0.046 against US$0.0205215 in ticks, about 2.3×. The reservation before the call still uses the full price, so a low cap (under about US$0.06) can abort a PASS. The per-run split and the tokens for the first 8 were not recorded. An offline adversarial check the same day found no bypass of the human gate in 11 cases. In production the approval has to arrive on an authenticated channel; this repo does not implement that channel. Before the fix, another sample n=8: 0/8 PASS, 8/8 INCOMPLETE, outbox=0, about US$0.15. The n=6 sample and the `happy_path` sample (0 bookings) stay as history.
- `no_cross_candidate_access` does not see an obfuscated email, an email split with spaces, or a first name alone. Offline check on 2026-10-17: 6/6 direct leaks detected and 3 clean controls (small n). `no_send_claim_without_outbox` on a new set, empty outbox, before counting `ningún`/`nada` (VERIFY_REPORT_11, HEAD `c525227`, n=20, small sample, not conclusive): recall 18/20, false positives 1/20. The measured false positive is "Ningún mail salió todavía…". After a real send, 0/20 of that set were flagged. VERIFY_REPORT_10, a different list, was 15/20 and 1/20; they are not comparable. Recall after counting `ningún`/`nada` is not measured yet. The `live` command prints `expect_failures`. The test suite clears `LIVE_LLM` and the keys, and fails if a test opens a socket.
- A date without an offset, such as `2026-04-14T00:00:00`, is rejected. It is not read as UTC or as Buenos Aires. The valid example is `2026-10-20T10:00:00-03:00`.
- The calendar and the emails are toys. The names (Candidata Uno, Ana Luz) are fictional.
- The FAQ search hit is on 30 questions written together with the texts. It is not generalization.
- Dockerfile is in the repo. It was not built in CI.

## In short

The model is expected to reason. The system around it is what makes the booking reliable. In CI the model is not there: a script stands in. What is present is the calendar that rejects a double booking, the person's confirmation of the exact slot, and the recruiter approval bound to the hash of the email. Turning the gates off on purpose makes the check exit 1. The invariants catch the broken case. A real model, when one is attached, has to pass through the same doors.
