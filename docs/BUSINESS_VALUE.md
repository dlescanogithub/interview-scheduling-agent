# Business value: interview scheduling with two gates

Taller Aurora is a fictional hiring co-op. It is not a client and not an employer. There is no fee and no contract. This plan uses only figures already in this repo. It does not add a volume, a wage, or a vendor price.

Labels:

- **MEASURED**: a command was run, or a live sample was recorded, on the date named.
- **[EST]**: the repo's own illustrative assumption, from [BUSINESS_CASE.md](BUSINESS_CASE.md).
- **SIMULATED**: the scripted provider and the default simulated prices. `SIM_PRICE_*` defaults to 0, so the scripted path costs 0 by construction. That 0 is not a market price.
- **UNVERIFIED**: not run for this revision. Live mode on code revision `25ad14d` is UNVERIFIED.

[BUSINESS_CASE.md](BUSINESS_CASE.md) states that none of its figures was measured in a workplace, and that the file contains no wage, no vendor price, and no currency amount. A dollar ROI is not computed here, because that would invent the wage the business case refuses to set.

## Buyer and problem

The buyer in the fixtures is a small hiring team. The person who feels the cost is the recruiter who drafts the slot emails, and the candidate who has to confirm the right hour in the right zone.

Today, in the **[EST]** baseline, the recruiter and the candidate trade about 6 messages and about 25 minutes of recruiter time per candidate until a slot sticks. With the gate on the mock, the candidate confirms one restated slot and the recruiter reviews that slot and the outbox row. The **[EST]** review is about 4 minutes. The agent does not remove the recruiter. It moves the recruiter from drafting to approving.

The second problem is a wrong invite: the right person and the wrong slot, or the reverse. The mock binds the recruiter's approval to a hash of the tool and its arguments. This repo does not claim that a model reduces wrong invites in a workplace. The business case says that explicitly. The harness result is in [METRICS.md](METRICS.md): on the scripted gate, `slot_inside_availability` and `book_preceded_by_user_confirmation` had 0 violations.

## Value levers

1. **Recruiter time [EST].** 25 minutes of ping-pong versus 4 minutes to approve a held slot, at 40 candidates a month, is about 14 recruiter-hours a month. The arithmetic is in the ROI section. If the volume is lower, or if the recruiter does not trust the calendar and re-checks for longer, the difference shrinks. Discovery question 4 exists for that reason.
2. **A wrong slot does not book on the mock.** The candidate confirms the exact slot. The recruiter approval covers that parameter hash and then expires. `book_slot` without that confirmation fails the gate, except in the deliberate regression, which is required to exit 1.
3. **An invite does not leave the process.** External tools write an in-memory outbox and nothing else. `EXTERNAL_TOOLS_ENABLED=0` blocks them, including during regression. There is no mailbox here, so there is no measured recall time. A real mailbox would add the recall work in [RUNBOOK.md](RUNBOOK.md).

These levers are properties of the harness. They are not a measured saving from a hiring team.

## Baseline vs target KPIs

Targets are goals, not results. The measured column is the scripted harness. The 2026-10-22 row is the remeasure on code revision `25ad14d`, Python 3.12.3. The 2026-10-17 rows are the record in [METRICS.md](METRICS.md). Simulated users means the YAML scenarios, not people.

| KPI | Baseline in the repo | Target in the repo | What was measured |
| --- | --- | --- | --- |
| Scenarios passing the invariant gate | 25/25 on commit `b684187`, 11 invariants, 0 violations (2026-10-17) | Gate stays green | **MEASURED** 2026-10-22: 26/26, 12 invariants, 0 violations |
| Forced regression | Exit 1 is the check | Must keep failing the approval invariant and the user-confirmation invariant | **MEASURED** 2026-10-22: exit 1, 54 violations |
| Handoff rate | 0.08 (2 of 25) on the 25-scenario run; 0.08 (2 of 26) after `booking_end_to_end` | Watched, not optimized against a fake provider | **MEASURED** 2026-10-22: 0.08 (2 of 26) |
| Mean turns to booking | 2.27 on the 25-scenario run; 2.25 on the 26-scenario runs | Keep the restatement short; no numeric promise | **MEASURED** 2026-10-22: 2.25 |
| Mean clarifications per booking | 0.00, with 2 clarify messages in the run | A clarify that does not end in a booking stays visible in `clarify_messages` | **MEASURED** 2026-10-22: 0.00, clarify messages 2 |
| Wrong-slot invariants | 0 violations of `slot_inside_availability` and `book_preceded_by_user_confirmation` on the gate | 0 | **MEASURED** 2026-10-22: 0 and 0 on the gate. The regression fails `book_preceded_by_user_confirmation` on 26 scenarios, which is the expected red result |
| Approval latency | not measured | A human queue. Do not invent a latency from the injected clock | not measured |
| Retrieval hit@1 / hit@3 | 30/30 and 30/30 on labels authored with the corpus. Bootstrap 95% [1.000, 1.000] | Not a generalization target | **MEASURED** 2026-10-22: the same 30/30 and 30/30. Not evidence of generalization |
| Live `booking_end_to_end` | 0/8 PASS before the approved-send change (2026-10-17) | A later sample on this revision, recorded with provider, model, date, and spend | **MEASURED** only on earlier commits: 15/15 PASS with a simulated approval, n=15, one model, 2026-10-17. **UNVERIFIED** on this revision |
| Tests and line coverage | 86 passed, combined coverage 90.37%, on `b684187` (2026-10-17) | CI stays at or above the 80% fail-under | **MEASURED** 2026-10-22: 124 passed; line coverage 93.95% (2780 of 2959 statements); pytest-cov total including branches 90.79% |

The live 15/15 is not a completion rate to sell. It is one model, a small n, a simulated approval, and the runtime executing the approved call. Detail and the earlier incomplete runs are in the README section "Live mode" and in [COST.md](COST.md).

## ROI model

All three inputs are **[EST]** from [BUSINESS_CASE.md](BUSINESS_CASE.md). None of them was measured in a workplace.

| Input | Value | Tag |
| --- | --- | --- |
| Candidates per month | 40 | [EST] |
| Recruiter minutes, manual ping-pong | 25 | [EST] |
| Recruiter minutes, approve a held slot | 4 | [EST] |
| Manual hours / month | 40 × 25 / 60 ≈ 16.7 | [EST] |
| Gated hours / month | 40 × 4 / 60 ≈ 2.7 | [EST] |
| Difference | ≈ 14 recruiter-hours / month | [EST] |

The 14 hours are not a measured saving. They fall out of those three inputs. The business case also says the difference shrinks if volume is 10 candidates, or if approval takes 15 minutes because the calendar is untrusted. It does not publish a second total for those cases. This file does not add one.

**Currency ROI:** not computed. The missing input is a loaded hourly rate, and [BUSINESS_CASE.md](BUSINESS_CASE.md) records no wage and no currency amount. Multiplying the 14 hours by an invented rate would contradict that file.

What would have to be true before anyone quoted a currency saving:

- Discovery replaces 40, 25, and 4 with the team's own counts.
- A wage is supplied by that team. It is not in this repo.
- The 4 minutes are still true after the recruiter has seen real calendar mistakes. If the person re-checks every field, the 4 minutes are the wrong input, and the hours should not be promised. The business case already says this in qualitative form.

## Cost table [EST]

This is the recruiter-time cost the repo is willing to write down. The unit is hours, not money. Every cell is **[EST]**.

| | Manual ping-pong | Gate on the mock |
| --- | ---: | ---: |
| Candidates / month | 40 | 40 |
| Recruiter minutes each | 25 | 4 |
| Recruiter hours / month | ≈ 16.7 | ≈ 2.7 |
| Difference | ≈ 14 recruiter-hours / month | |

There is no **[EST]** row for software dollars, integration hours, or a vendor tariff. Adding one would invent a number. [COST.md](COST.md) is the software-cost record, and it is not an estimate:

| Path | Cost | Tag |
| --- | --- | --- |
| CI eval and the scripted demo | 0, because `SIM_PRICE_*` defaults to 0 | SIMULATED accounting, not a market price. **MEASURED** again on 2026-10-22 as a 26/26 gate with no provider call |
| Live samples on 2026-10-17 | The rows in [COST.md](COST.md). The PASS slice sums are about US$0.11, US$0.054, US$0.06728, US$0.05378, and US$0.0205215, on the commits named there. Aborted-cap spend on VERIFY_REPORT_11 is US$0.0464288 | **MEASURED** on those commits. Not a price list |
| Live mode on this revision | not run | **UNVERIFIED** |

Latency is not in the cost. The lab clock is injected and must not be reported as latency.

## Measurement plan

What this repo can check on every change, at cost zero:

1. `python3 -m pytest` for the unit and integration tests and the coverage fail-under of 80%.
2. `python3 -m scheduling_agent eval` exits 0.
3. `python3 -m scheduling_agent eval --regression` exits 1, and the failures include the approval invariant and the user-confirmation invariant.
4. `python3 -m ruff check .`, `python3 -m ruff format --check .`, and `python3 -m mypy src`.
5. `python3 -m scheduling_agent.secretscan` reports no findings.
6. Tests must not open a socket. Demo and eval stay on the scripted provider.

What a team would still have to measure, because this repo does not:

| Question | Why it is open |
| --- | --- |
| Do recruiters actually spend 4 minutes, or do they re-check the calendar? | The 4 minutes are [EST]. Approval latency is not measured |
| How many candidates a month, and how many messages? | 40 and about 6 messages are [EST] |
| Does a wrong invite still get through once a real mailbox exists? | The harness wrong-slot count is not a workplace rate. The business case says not to claim a model reduces wrong invites |
| Does the send-claim check catch a live model's wording, including `ningún` / `nada`? | Recall after that change is not measured. Earlier sets are small and not comparable with each other |
| What does a live run on this revision cost and pass? | **UNVERIFIED**. The 2026-10-17 sample is a different tree |
| Is the candidate who is speaking authenticated? | Out of scope. The session is assumed to know |
| Accessibility and load | Design only. Not tested with people |

A shadow phase, where the agent proposes slots and a person still sends every message, is design only ([SCOPE.md](SCOPE.md)). The exit criteria in that file are harness criteria. They are not exit criteria for a rollout.

## Risks

Qualitative labels come from [RISKS.md](RISKS.md). No probabilities were measured.

| Risk | Why it matters for the value story | What the repo already does |
| --- | --- | --- |
| Wrong invite | The hours model ignores this cost. A single wrong invite can dominate 14 hours | User restatement, approval bound to the parameter hash, recall steps in the runbook. The channel that would carry a real approval is not implemented |
| The 4 minutes are optimistic | If approval takes 15 minutes, the [EST] difference shrinks. The repo states that and does not publish a replacement total | Discovery question 4 |
| Simulated approval mistaken for a person | The demo and the scenario inject the recruiter decision. Certain in this repo | Copy in the README. Offline check on 2026-10-17: no human-gate bypass in 11 cases (small n) |
| Over-trust in the scripted brain | Someone reads 26/26 or 15/15 as model quality | CI brain is the scripted provider. Live on this revision is UNVERIFIED. 15/15 does not prove the model retries the tool |
| Send-claim misses | The model can say the mail went out while the outbox is empty | Heuristic, with the limits in the README. Recall after `ningún` / `nada` is not measured |
| Cross-candidate mention the check misses | An obfuscated address, a spaced address, or a first name alone | Direct name, address, and id are checked. The misses are documented. Offline on 2026-10-17: 6/6 direct leaks, 3 clean controls, small n |
| Double booking if a second writer bypasses the mock | The hours model assumes one calendar | Overlap check inside the mock, including the buffer, and an invariant on the final snapshot |
| Time-zone error | A candidate in another zone confirms the wrong clock | Every time shown to the user includes a zone. Naive datetimes are rejected |
| Injected instruction in a note or the FAQ | Retrieved text could be treated as an order | Retrieved text is data. The poison FAQ is a fixture. The effect ceiling is an invariant |
| Candidate data in logs | A real mailbox copied into a trace | Addresses minimized to `[email]` in the trace. Secret-shaped strings redacted |

Not covered, and not given a probability here: a review of a real identity provider, a penetration test, and a data-processing agreement.

## MEASURED vs not

**MEASURED**

- 2026-10-22, Python 3.12.3, pytest 9.1.1, code revision `25ad14d`: 124 passed; line coverage 93.95% (2780 of 2959 statements); pytest-cov total including branches 90.79%; eval 26/26 with 0 violations; regression exit 1 with 54 violations; ruff and mypy clean; secret scan with no findings. The same run's simulated-user and retrieval lines match the latest 26-scenario record.
- 2026-10-17 scripted history in [METRICS.md](METRICS.md), including the earlier 25/25 gate and the test counts from 86 passed upward. Those commits are not re-labeled as today's run.
- 2026-10-17 live samples in [COST.md](COST.md) and the README: the path from the incomplete n=8 to 15/15 PASS with a simulated approval, the aborted caps, the token counts that were recorded, and the ones that were not.
- Heuristic checks on fixed lists, with n and the commit named next to each rate. They are small samples, not a trend.

**Not measured, and not filled in**

- A wage, a currency ROI, a vendor price list, and any cost other than the recorded live ticks plus the simulated 0.
- Approval latency, recruiter minutes on a real queue, and wrong-invite counts outside the scripted gate.
- Live mode on this revision, including whether the model retries the tool and whether the send-claim recall holds after `ningún` / `nada`.
- Generalization of the FAQ retrieval. The labels were written with the corpus.
- Accessibility, load, wall-clock latency, a real calendar, a real mailbox, and candidate authentication.
- Docker image build on 2026-10-22.
