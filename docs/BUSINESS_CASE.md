# Business case

All figures in this file are **[EST]**. None of them was measured in a workplace. Taller Aurora is fictional. There is no fee, no contract, and no client.

## Baseline

A recruiter and a candidate trade email until a slot sticks. [EST] that ping-pong is about 6 messages and about 25 minutes of recruiter time per candidate.

## With the gate on the mock

The candidate confirms one restated slot. The recruiter reviews that slot and approves or rejects the outbox row. [EST] that review is about 4 minutes per candidate. The agent does not remove the recruiter. It moves the recruiter from drafting to approving.

## Formula

| Input | Value | Tag |
| --- | --- | --- |
| Candidates per month | 40 | [EST] |
| Recruiter minutes, manual ping-pong | 25 | [EST] |
| Recruiter minutes, approve a held slot | 4 | [EST] |
| Manual hours / month | 40 × 25 / 60 ≈ 16.7 | [EST] |
| Gated hours / month | 40 × 4 / 60 ≈ 2.7 | [EST] |
| Difference | ≈ 14 recruiter-hours / month | [EST] |

The 14 hours are not a measured saving. They fall out of the three [EST] inputs above. If volume is 10 candidates, or if approval takes 15 minutes because the calendar is untrusted, the difference shrinks. Discovery question 4 exists for that reason.

## What this does not claim

- No wage, no vendor price, no currency amount.
- No claim that a model reduces wrong invites. The mock gate's wrong-slot count on the scripted scenarios is a harness result, reported in [METRICS.md](METRICS.md).
- A real mailbox would add recall work. See [RUNBOOK.md](RUNBOOK.md).
