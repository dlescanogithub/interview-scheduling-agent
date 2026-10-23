# interview-scheduling-agent

## Start here

This lab proves the gates around a scripted scheduler: a slot is booked only after the candidate confirms that exact slot, and an invite stays in an in-memory outbox until a recruiter approves that same call. It does not prove model quality. Live mode on this revision is **UNVERIFIED**.
Offline demo, no key and no network: `python3 -m scheduling_agent demo`
- **Demo video (English, offline):** [docs/demo/README.md](docs/demo/README.md) — [`interview_scheduling_agent_demo_en.mp4`](docs/demo/interview_scheduling_agent_demo_en.mp4)
Walkthrough and limits: [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

Taller Aurora, the hiring co-op in the fixtures, is fictional. The brain that runs in CI and in `demo` is a scripted provider. Tests clear `LIVE_LLM`, `LLM_*`, `XAI_API_KEY`, and `MAX_LIVE_SPEND_USD`, and a socket guard fails the run if a test opens a connection.

## Problem

A recruiter and a candidate trade email until a slot sticks. The expensive mistakes are a wrong slot and an invite that leaves before anyone approves that exact call.

On the mock, the candidate confirms one restated slot (date, weekday, time, and zone). The recruiter then approves or rejects that outbox row. The approval is bound to a hash of the tool and its arguments: an approval of 10:00 does not cover 11:00. The recruiter step in this repo is simulated. A real deployment would need that approval on an authenticated channel, and this repo does not implement that channel.

## Architecture

```mermaid
flowchart LR
  user[Candidate] --> loop[Bounded loop]
  loop --> policy[Scripted provider]
  policy --> gate[Tool gateway]
  gate --> cal[Mock calendar]
  gate --> faq[Local BM25]
  gate --> human[User confirm and recruiter approval]
  human --> outbox[In-memory outbox]
```

The mock calendar holds a slot with a TTL, a 45-minute duration, and a 15-minute buffer, and it returns at most three options. External tools (`send_invite_email`, `send_reschedule_email`, `send_cancellation_notice`) write only to the in-memory outbox, and only after a matching approval. `book_slot` also requires the candidate's confirmation of that same slot, unless the process is the deliberate regression (`eval --regression`). `EXTERNAL_TOOLS_ENABLED=0` blocks external tools even then.

The eval gate scores invariants on the trace, not an exact list of tool calls. Twelve invariants, all 26 pass on the 2026-10-22 run recorded in [Proof](#proof):

`no_double_booking`, `slot_inside_availability`, `no_external_without_matching_approval`, `no_send_claim_without_outbox`, `book_preceded_by_user_confirmation`, `times_include_timezone`, `at_most_three_options`, `no_cross_candidate_access`, `faq_citations_or_unknown`, `within_budgets`, `safe_state_after_rejection`, `injection_effect_ceiling`.

## Quickstart

Default cost: zero. No API key. Tests do not use the network.

```bash
python3 -m pip install -e ".[dev]"
python3 -m scheduling_agent demo
python3 -m pytest
python3 -m scheduling_agent eval
```

`python3 -m scheduling_agent eval --regression` is expected to exit 1. That exit code is the check.

| Make | Plain command |
| --- | --- |
| `make setup` | `python3 -m pip install -e ".[dev]"` |
| `make lint` | `python3 -m ruff check .` and `python3 -m ruff format --check .` |
| `make format` | `python3 -m ruff format .` and `python3 -m ruff check --fix .` |
| `make test` | `python3 -m pytest` |
| `make eval` | `python3 -m scheduling_agent eval` |
| `make eval-regression` | `python3 -m scheduling_agent eval --regression` |
| `make secretscan` | `python3 -m scheduling_agent.secretscan` |
| `make demo` | `python3 -m scheduling_agent demo` |
| `make live` | `python3 -m scheduling_agent live --scenario booking_end_to_end --max-turns 12` |

`make live` calls a provider only when live mode is configured. It was not run for this revision. See [Live mode](#live-mode).

## Use cases, governance and business strategy

### Client-style use cases (fictional, inspired by a pattern, no real client)

| Use case | Status | Problem | Who approves | Gated effects | How this repo handles it |
| --- | --- | --- | --- | --- | --- |
| Interview scheduling for a small hiring team | Implemented as a mock | Slot ping-pong and a wrong invite | Recruiter, after the candidate confirms the slot | `book_slot`; invite, reschedule, and cancel emails | Mock calendar, two gates, in-memory outbox |
| Appointment booking for a clinic-style service | Design only | The same hold-and-confirm pattern, different nouns | A clinician or front desk | Book and a patient notice | Not built. The same gates would apply |
| Internal meeting-room or equipment booking | Design only | A shared resource and a double booking | The resource owner | Book and a notice to the requester | Not built |

### Personal use cases

| Use case | Status | Problem | Who approves | Gated effects | How this repo handles it |
| --- | --- | --- | --- | --- | --- |
| Personal assistant that never sends without an OK | Design only | A draft leaves before the owner reads it | The owner | Any external send | The recruiter gate is the same shape. Not built for a personal calendar |
| Study-session planner | Design only | Finding a free block with a partner | The person whose calendar it is | A calendar write and a message | Not built |

### Governance checklist

| Control | Where |
| --- | --- |
| Human approval before an external tool | `src/scheduling_agent/approvals.py`, `src/scheduling_agent/tools.py` |
| Approval bound to a hash, then expiry | `src/scheduling_agent/approvals.py` |
| User confirmation of the same slot | `src/scheduling_agent/tools.py`, `src/scheduling_agent/agent.py` |
| Trace and JSON logs | `src/scheduling_agent/trace.py`, `src/scheduling_agent/logging_setup.py` |
| Outbox instead of a real send | `src/scheduling_agent/runtime.py` |
| Kill switch `EXTERNAL_TOOLS_ENABLED=0` | `src/scheduling_agent/tools.py` |
| Risks | [docs/RISKS.md](docs/RISKS.md) |
| Costs | [docs/COST.md](docs/COST.md) |
| Incident, recall, rollback | [docs/RUNBOOK.md](docs/RUNBOOK.md) |

Not covered yet: candidate authentication, a real calendar or mailbox, embeddings, WhatsApp or voice, accessibility testing with people, load testing.

### Business strategy

The business problem is recruiter time spent on slot ping-pong, and the cost of a wrong invite. The hours model is **[EST]** in [docs/BUSINESS_CASE.md](docs/BUSINESS_CASE.md): about 14 recruiter-hours a month from 40 candidates, 25 minutes of ping-pong, and 4 minutes to approve a held slot. There is no wage in that file, so there is no currency ROI. Phased rollout is in [docs/SCOPE.md](docs/SCOPE.md). Success metrics are in [docs/METRICS.md](docs/METRICS.md). The value plan that stays inside those documents is [docs/BUSINESS_VALUE.md](docs/BUSINESS_VALUE.md).

Deployment conversation: start with discovery ([docs/DISCOVERY.md](docs/DISCOVERY.md)), then a shadow period where a person still sends every message, then turn the gate on against a mock, and only then talk about a real calendar. The recruiter owns the invite. The operator owns the kill switch, the spend cap, and the ledger. The candidate owns the yes on the slot. Shadow mode and a real calendar are design only ([docs/SCOPE.md](docs/SCOPE.md)).

### Design-only vs implemented

| Capability | Status |
| --- | --- |
| Mock calendar, holds with TTL, buffers, zones | Implemented |
| Two human gates and parameter-hash binding | Implemented |
| External tools writing only to an in-memory outbox | Implemented |
| Kill switch | Implemented |
| Local BM25 over a synthetic FAQ | Implemented |
| Invariant gate and forced regression | Implemented |
| Optional live adapter, off by default | Code is in the tree. A live call on this revision is **UNVERIFIED**. The last **MEASURED** sample is 2026-10-17, on earlier commits, in [Live mode](#live-mode) |
| Google or Microsoft calendar and email | Design only |
| ATS integration | Design only |
| Candidate authentication | Design only |
| Embeddings or a vector index | Design only |
| WhatsApp or voice | Design only |
| Accessibility testing with people | Design only |
| Load testing | Design only |

Dockerfile is in the repo. The image was not built as part of the 2026-10-23 measurement (**UNVERIFIED**).

## Business value

The buyer in the fixtures is Taller Aurora, a fictional hiring co-op. The value lever the repo actually prices is recruiter time: **[EST]** about 14 recruiter-hours a month if 40 candidates move from about 25 minutes of email ping-pong to about 4 minutes reviewing a slot the candidate already confirmed. No wage, vendor price, or currency amount is in [docs/BUSINESS_CASE.md](docs/BUSINESS_CASE.md), so this repo does not state a dollar ROI.

The scripted path costs 0 because `SIM_PRICE_*` defaults to 0. That 0 is simulated accounting, not a market price. Live spend that was measured on 2026-10-17 is in [docs/COST.md](docs/COST.md). Live spend on this revision was not measured.

Full plan, with the hours formula, the KPI table, and what is **MEASURED** versus not: [docs/BUSINESS_VALUE.md](docs/BUSINESS_VALUE.md).

## Proof

**MEASURED** 2026-10-23. Package `scheduling_agent` 0.1.1. Code revision `0204f8b` (the docs commit that cites this revision does not change the package). Python 3.12.3. pytest 9.1.1. ruff 0.17.2. mypy 2.4.0. One local run each. Not a benchmark suite. CI is configured for Python 3.11 and 3.12; Python 3.11 was not re-run today.

Command:

```bash
python3 -m pytest
```

`pyproject.toml` adds `--cov=scheduling_agent --cov-report=term-missing --cov-fail-under=80`. Branch coverage is on (`[tool.coverage.run] branch = true`). The same process also wrote a JSON report so statement coverage could be read separately.

| Check | Result |
| --- | --- |
| Tests | **125 passed** |
| Line coverage | **94.12%** (2754 of 2926 statements). coverage.py `percent_statements_covered` is 94.12166780587833 |
| pytest-cov total, statements plus branches | **91.02%** (printed `Total coverage: 91.02%`; `percent_covered` 91.01601601601601) |
| Branch coverage on that run | 82.52% (883 of 1070 branches; 157 partial). `percent_branches_covered` 82.5233644859813 |
| Eval gate | **26/26** pass, 12 invariants, **0** violations. `python3 -m scheduling_agent eval` |
| Forced regression | exit **1**, **54** violations (25 approval, 2 send-claim lines on `kill_switch`, 26 confirmation, 1 safe-state). `python3 -m scheduling_agent eval --regression` |
| Lint | ruff check and format check passed |
| Types | mypy, 25 source files, no issues |
| Secret scan | `secret scan: no findings` |

The percentages above are the totals coverage.py printed for that run. The 2026-10-22 run printed `CoverageWarning: Module scheduling_agent was previously imported, but not measured`. This 2026-10-23 run did not print that warning.

Simulated users on that eval (the 26 YAML scenarios, not people): mean turns to booking 2.25, mean clarifications per booking 0.00, clarify messages 2, handoff rate 0.08 (2 of 26). Retrieval, 30 English queries whose labels were written together with the English corpus: hit@1 30/30, hit@3 30/30. The bootstrap 95% interval is [1.000, 1.000] because every item is a hit. Resampling this list is not a model comparison and is not evidence of generalization. The previous 30/30 on the bilingual corpus (2026-10-22 and earlier) is previous data. This 30/30 was remeasured on the English corpus on 2026-10-23.

Earlier measurements stay in [docs/METRICS.md](docs/METRICS.md). The historical "coverage" percentages below are that pytest-cov total (statements plus branches), not the statement-only percentage. They were not recomputed as line coverage on 2026-10-23. The 2026-10-22 row is the previous tree: 124 passed, statement coverage 93.95% (2780 of 2959), pytest-cov total 90.79%.

| Date | Commit | pytest | pytest-cov total | Eval | Regression |
| --- | --- | --- | --- | --- | --- |
| 2026-10-17 | `b684187e418dc0bd230117841ff8f6b4a6559fd2` | 86 passed | 90.37% | 25/25, 11 invariants, 0 violations. Mean turns to booking 2.27, mean clarifications per booking 0.00, clarify messages 2, handoff rate 0.08 (2 of 25) | exit 1, 50 violations |
| 2026-10-17 | `f94f39c63951ddddbdfc2992ef0e0f375160c034` | 93 passed | 90.85% | 25/25, 0 violations | exit 1, 50 violations |
| 2026-10-17 | `b9c04708ea72816ebd63cb37f8c7b3b0f2f71408` | 103 passed | 91.04% | 26/26, 0 violations. Mean turns 2.25, handoff rate 0.08 (2 of 26) | exit 1, 52 violations |
| 2026-10-17 | `87eb459a88846f58b85cf0f93520afb1fbae4d52` | 108 passed | 91.07% | 26/26, 0 violations | exit 1, 52 violations |
| 2026-10-17 | `afc5f6d96fe99e70bb5d677e3d2b75e5489b5550` | 114 passed | 90.60% | 26/26, 12 invariants, 0 violations. Mean turns 2.25, handoff rate 0.08 (2 of 26) | exit 1, 54 violations |
| 2026-10-17 | `9b11c77fea78a8ee2d31864a0fb6e729e1ee8453` | 116 passed | 90.68% | 26/26, 0 violations | exit 1, 54 violations |
| 2026-10-17 | `bcfd136d8dbbbcdcb9597e96601eee8563c7d620` | 118 passed | 90.65% | 26/26, 0 violations | exit 1, 54 violations |
| 2026-10-17 | `a9b21e5388fafdaaf0b4fa3dd5f5c440ecaf9948` | 120 passed | 90.77% | 26/26, 0 violations | exit 1, 54 violations |
| 2026-10-17 | `cc5c233ea771e218f4bb2f28c2df503889db0917` | 122 passed | 90.79% | 26/26, 0 violations | exit 1, 54 violations |
| 2026-10-17 | `ab4e24617f1250074ffe998892c0267d5f179aa3` | 124 passed | 90.79% | 26/26, 0 violations | exit 1, 54 violations |
| 2026-10-22 | `25ad14d` | 124 passed | 90.79% | 26/26, 0 violations. Mean turns 2.25, clarify messages 2, handoff rate 0.08 (2 of 26) | exit 1, 54 violations |

Package `scheduling_agent` 0.1.0 for every row in that table. Python 3.12.3 is what the original note named for `ab4e246`, for the rows written as that same package and Python (`f94f39c`, `b9c0470`, `87eb459`), and for the rows [docs/METRICS.md](docs/METRICS.md) marks 3.12.3. The `b684187` row did not name a Python version. The 2026-10-22 row used Python 3.12.3 and pytest 9.1.1. Where the original note said so, ruff, the format check, mypy, and the secret scan passed. The table collects those published rows. It does not assert git parent order. Today's run is package 0.1.1 and is the proof section above, not a row in this table.

## Live mode

**Live mode on this revision: UNVERIFIED.** No live provider call was made on 2026-10-23, and none was made on code revision `0204f8b`. The sample below is **MEASURED** on 2026-10-17, on earlier commits, before the cached-price ledger row. The send-claim rates in that sample were measured on the previous Spanish wording. They do not measure the English detector. The sample does not verify this tree.

Model for every row: `grok-4.20-0309-non-reasoning`. One model. Small samples, not a rate. Cost figures that name `usage.cost_in_usd_ticks` come from that field. Per-run splits and token counts for the first eight PASS runs were not recorded. A PASS still requires `task_completed=true`: the booking, an invite in the outbox, the approval, and clean invariants. The runtime executes the approved call. These runs do not prove that the model retries the tool.

| Sample | Commit | Result | Cost |
| --- | --- | --- | --- |
| `happy_path`, 3 runs | that day's main, before the scenario asked for the second yes | INCOMPLETE 3/3, exit 3, 0 bookings. The scenario ended on the first "Yes, I confirm." (the 2026-10-17 run used the previous Spanish wording of that sentence), so `book_slot` never ran. 4 calls each. Tokens not recorded | US$0.00875 + US$0.00872 + US$0.00844 = US$0.02591 |
| `booking_end_to_end`, n=6 | same day, before the cross-candidate fix | 6/6 booked `book-0002`; 3 INCOMPLETE without `send_invite_email`; 3 FAIL on a cross-candidate false positive; no PASS | about US$0.07 |
| `booking_end_to_end`, n=8, before the approved-send change | that day's main | 0/8 PASS, 8/8 INCOMPLETE, 0 FAIL, 0 false positives of `no_cross_candidate_access`, outbox count 0 | about US$0.15 |
| `booking_end_to_end`, n=5, after the approved-send change | that day's main | 5/5 PASS with a simulated approval (outbox count 1, origin approval, same parameter hash) | about US$0.11 |
| `booking_end_to_end`, 3 more runs the same day | that day's main | PASS 3/3. With the n=5 row, 8/8 PASS with a simulated approval | US$0.054 |
| VERIFY_REPORT_9, 3 runs | `4c2170d`, Python 3.12.15 | PASS 3/3, exit 0, `expect_failures: none`, parameter hash `f69ebd9b` (origin approval), outbox `out-0004`. 28 calls, 0 errors; 30–36k tokens in, 612–779 out per run. With the earlier 8, 11/11 PASS with a simulated approval | US$0.02512 + US$0.02060 + US$0.02156 = US$0.06728 |
| VERIFY_REPORT_10, 3 runs | `bb314c9`, Python 3.12.15 | PASS 3/3, exit 0, `expect_failures: none`, same hash and outbox id. 27 calls, 0 errors; about 31k tokens in, 625–714 out per run. With the earlier 11, 14/14 PASS with a simulated approval | US$0.01766 + US$0.02300 + US$0.01312 = US$0.05378 |
| VERIFY_REPORT_11, 1 PASS | `c525227`, Python 3.12.15 | PASS, exit 0, `expect_failures: none`, `task_completed=true`, same hash and outbox id. 10 calls, 35629 tokens in (24576 cached), 716 out. With the earlier 14, 15/15 PASS with a simulated approval, n=15 | US$0.0205215 |
| VERIFY_REPORT_11, 4 aborted runs | `c525227` | INCOMPLETE, `cost_cap` before the send, invariants passed, outbox count 0. Not PASS and not FAIL. Caps were the verifier's: US$0.028 three times (18 calls, US$0.0347365) and US$0.035 once (7 calls, US$0.0116923) | US$0.0464288 |

Each report's combined spend includes other repos. This repo's slice of VERIFY_REPORT_9 is US$0.06728. VERIFY_REPORT_10's report total is US$0.06837 and this repo's slice is US$0.05378. VERIFY_REPORT_11's report total is about US$0.0770; this repo's slice is the US$0.0205215 PASS plus US$0.0464288 on the aborted caps.

On that PASS the ledger's full input price estimated about US$0.046 versus US$0.0205215 in ticks, about 2.3×, because 24576 prompt tokens were cached. The verifier's price note was US$1.25 / US$0.20 cached / US$2.50 out per million. `LLM_PRICE_CACHED_PER_MTOK` discounts the settled row. The reservation before the call still uses the full input price and `estimate × 2`, so a cap under about US$0.06 can abort a run the tick cost would have allowed. The PASS used a cap of US$0.06.

An offline adversarial check the same day found no bypass of the human gate in 11 cases (small n). `no_cross_candidate_access` still misses an obfuscated address, an address with spaces, and a first name alone. An offline check that day detected 6/6 direct leaks and passed 3 clean controls (small n).

`no_send_claim_without_outbox` is a heuristic. The sets are different lists, so the rates are not a trend:

| When | n | Caught or recall | False positives |
| --- | --- | --- | --- |
| Fresh forms before the verb-and-object detector, empty outbox | 14 caught-set, 9 clean | 2/14 | 0/9 |
| VERIFY_REPORT_9, HEAD `4c2170d`, before the verb expansion | 20 | 15/20 | 1/20 |
| VERIFY_REPORT_10, HEAD `bb314c9`, before the word-boundary fix | 20 | 15/20 | 1/20 |
| VERIFY_REPORT_11, HEAD `c525227`, previous Spanish wording, before "none" / "nothing" | 20 | 18/20 | 1/20 |

After a real send, 0/20 of each of those three n=20 sets were flagged. The two 15/20 figures are not comparable. VERIFY_REPORT_11 also re-scored the VERIFY_REPORT_10 list at 20/20 with 0/20 false positives; that re-score is not independent, because the tests use those literals. The n=20 sets are small, not conclusive (the 18/20 note says about ±15 points). Those rates were measured on the previous Spanish wording. They do not measure the English detector. No new n=20 recall was run on 2026-10-23.

The false positive on the 18/20 set, in English, was "No email has gone out yet; the draft is still under review." Two quoted misses stay out of the tests: "it is already in your inbox" has no send verb, and "the invitation already went out to your email" was hidden because the 48-character lookback started inside the previous wording's word for appointment and the slice began with "no". Negation uses a whole word, so a longer word that merely contains those letters does not hide a completed send. An offer question ("Would you like me to send…?") stays pending.

External pytest checks that day, with `LIVE_LLM=1` and a fake key, made 0 calls to the provider host: HEAD `bcfd136` (VERIFY_REPORT_9, Python 3.12.15) 118 passed, combined coverage 90.65%; the previous commit `4d512df` in that environment failed 2 tests and made 6 calls. HEAD `bb314c9` (VERIFY_REPORT_10) 120 passed, 90.77%. HEAD `c525227` (VERIFY_REPORT_11) 122 passed, 90.79%.

## What this does NOT prove

- Live mode on this revision is **UNVERIFIED**. The 15/15 PASS figure is a 2026-10-17 sample on earlier commits, one model, n=15, with a simulated approval. It is not a rate, and it does not verify the later detector or ledger changes.
- It does not prove the model retries a tool. The runtime executes the stored approved call.
- It does not prove model quality. CI and `demo` use the scripted provider.
- It does not prove a real calendar write, a real email, or candidate authentication.
- It does not prove accessibility, load, or wall-clock latency. The lab clock is injected. Latency columns in [docs/COST.md](docs/COST.md) are not measured.
- It does not prove the send-claim heuristic. The 2026-10-17 recall figures were measured on the previous Spanish wording. No new n=20 recall was run for the English detector. The check misses an obfuscated address, a spaced address, and a first name alone.
- It does not prove retrieval generalizes. The 30/30 hit rate is on labels written with the corpus.
- It does not prove a currency saving. [docs/BUSINESS_CASE.md](docs/BUSINESS_CASE.md) records no wage. The 14 recruiter-hours are **[EST]**, and they fall out of three assumed inputs.
- It does not prove an authenticated recruiter channel. The approval in the scenario and the demo is simulated. An offline check found no human-gate bypass in 11 cases. That is a small n.
- A green `eval --regression` would mean the gate is broken. The 2026-10-23 run exited 1, which is the expected result.

## Decisions

- [0001 Scripted provider in CI](docs/adr/0001-scripted-provider-in-ci.md)
- [0002 Invariants, not exact trajectories](docs/adr/0002-invariants-not-trajectories.md)
- [0003 Two confirmations](docs/adr/0003-two-confirmations.md)
- [0004 Local BM25](docs/adr/0004-local-bm25.md)
- [0005 Effect classes, kill switch, and cancel](docs/adr/0005-effect-classes-and-kill-switch.md)
- [0006 Reject naive datetimes](docs/adr/0006-reject-naive-datetimes.md)
- [0007 Pending slot and zoned times](docs/adr/0007-pending-slot-and-zoned-times.md)

## Security and known limits

Threat notes: [SECURITY.md](SECURITY.md). Configuration comes from the environment. `.env` is git-ignored. Do not commit keys, tokens, or live ledgers.

A naive datetime such as `2026-04-14T00:00:00` is rejected. It is not read as UTC or as Buenos Aires. A zoned example is `2026-10-20T10:00:00-03:00`.

## Next steps

- A live run on this revision, with provider, model, date, command, and spend recorded, is still **UNVERIFIED**. The English send-claim detector has no new n=20 recall. The 2026-10-17 rates are previous data. Template: [docs/LIVE_RUN_TEMPLATE.md](docs/LIVE_RUN_TEMPLATE.md).
- Keep retrieval labels written apart from the documents before claiming anything about generalization.
- Shadow a real calendar only after discovery, with the same gates and the kill switch still in the operator's hands.

## Docs

| Doc | What it is for |
| --- | --- |
| [docs/demo/README.md](docs/demo/README.md) | Demo video (English, offline) |
| [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) | Walkthrough for engineers and buyers |
| [docs/BUSINESS_VALUE.md](docs/BUSINESS_VALUE.md) | Value plan inside the repo's own [EST] hours model |
| [docs/BUSINESS_CASE.md](docs/BUSINESS_CASE.md) | Recruiter-hours formula, all figures [EST], no wage |
| [docs/DISCOVERY.md](docs/DISCOVERY.md) | Ten questions and what the answer changes |
| [docs/SCOPE.md](docs/SCOPE.md) | Phases, out of scope, exit criteria for the mock |
| [docs/RISKS.md](docs/RISKS.md) | Qualitative probability, impact, mitigation, owner |
| [docs/METRICS.md](docs/METRICS.md) | What was measured, and the targets that are not results |
| [docs/COST.md](docs/COST.md) | Scripted cost 0, plus the 2026-10-17 live rows |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Kill switch, recall, rollback |
| [docs/architecture.md](docs/architecture.md) | Module map |
| [docs/UX_PRINCIPLES.md](docs/UX_PRINCIPLES.md) | How the dialogue is supposed to behave |
| [docs/ADAPT_TO_A_REAL_CLIENT.md](docs/ADAPT_TO_A_REAL_CLIENT.md) | What to throw away first |
| [docs/LIVE_RUN_TEMPLATE.md](docs/LIVE_RUN_TEMPLATE.md) | What a later live run has to record |
| [docs/PROVENANCE.md](docs/PROVENANCE.md) | Shared utilities and the fictional co-op |
| [SECURITY.md](SECURITY.md) | Reporting and the controls that exist here |
| [CHANGELOG.md](CHANGELOG.md) | What changed |

## Authorship and how this was built

This repository was built with AI-assisted development.

**What I did (Diego Lescano):**

- Chose the problem and the scope: which failure to show, what is out of scope, and what the repo must not claim.
- Set the governance and business-strategy requirements: approval controls, traceability, risks and costs, the estimated hours model, rollout, and metrics.
- Set the engineering standards: Python, tests, CI, synthetic data only, no real client or employer data.
- Reviewed what became public, and decided to keep the failed live runs and the small-sample limits in the record.

**What AI coding agents did:**

- Wrote most of the code, tests, and documentation from those briefs, under review.

**What this repo does not claim:**

- It is not a production system, and every data set is synthetic.
- Live numbers come from a small sample, one model, and earlier commits. They are indicative. Live mode on this revision is UNVERIFIED.
