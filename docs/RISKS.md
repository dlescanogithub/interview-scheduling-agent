# Risks

Qualitative labels only. No measured probabilities.

| Risk | Probability | Impact | Mitigation | Owner |
| --- | --- | --- | --- | --- |
| Wrong invite (right person, wrong slot, or the reverse) | Medium if a real mailbox is attached; low on the mock because the hash must match | High | User restatement, recruiter approval bound to the parameter hash, recall steps in the runbook | Recruiter |
| Double booking | Low while the calendar itself rejects overlaps; higher if a second writer bypasses it | High | Overlap check inside the calendar, including buffer; invariant on the final snapshot | Operator |
| Time-zone error | Medium when the candidate's zone is not the interviewer's | High | Every time shown to the user includes a zone; both clocks are in the slot view | Operator |
| Injected instruction in a note or in the FAQ | Medium as soon as free text is retrieved | High | Retrieved text is data. Injection calls cannot execute an effect above what the user asked. Poison document is a fixture | Operator |
| Over-trust in the agent | High if someone reads the demo as a model evaluation | High | README states the CI brain is a scripted provider. On 2026-10-17, `booking_end_to_end`, n=5, one model: 5/5 PASS with a simulated approval. That does not prove the model retries the tool, because the runtime executes the approved call. Small sample, not a rate | Owner of the repo |
| Simulated recruiter approval | Certain in this repo: the scenario and the demo inject the decision | High if that injection is mistaken for a person | In production the approval has to arrive on an authenticated channel. This repo does not implement that channel. Offline adversarial check 2026-10-17: the human gate was not bypassed in 11 cases (small n) | Operator |
| Candidate PII in logs or traces | Medium if a real mailbox is copied into the trace | High | Emails minimized to `[email]` in the trace; secret-shaped strings redacted; ledger must not contain the API key | Operator |
| Cross-candidate mention the check misses | Medium if the model obfuscates | High for privacy, low on this fictional roster | `no_cross_candidate_access` matches a direct name, address, or id. It misses an obfuscated address, an address with spaces, and a first name alone. Offline on 2026-10-17: 6/6 direct leaks detected, 3 clean controls, small n | Operator |
| Telling the candidate the invite went out | High on the 2026-10-17 n=8 sample: the model said the email was approved and sent while outbox=0 | High | Offline the same day, empty outbox, before the pattern change: `no_send_claim_without_outbox` caught 9/14 send-claim forms. It missed `se envió el email`, `fue enviado`, `te enviamos`, `I sent you`, and `went out`. False positives 2/9 on pending future wording: `will be emailed`, `quedará en la bandeja de salida`. Small n. Recall after the pattern change: not measured yet | Operator |

Not covered yet: a review of a real identity provider, a penetration test, and a data-processing agreement. Those are outside this lab.
