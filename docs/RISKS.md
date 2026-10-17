# Risks

Qualitative labels only. No measured probabilities.

| Risk | Probability | Impact | Mitigation | Owner |
| --- | --- | --- | --- | --- |
| Wrong invite (right person, wrong slot, or the reverse) | Medium if a real mailbox is attached; low on the mock because the hash must match | High | User restatement, recruiter approval bound to the parameter hash, recall steps in the runbook | Recruiter |
| Double booking | Low while the calendar itself rejects overlaps; higher if a second writer bypasses it | High | Overlap check inside the calendar, including buffer; invariant on the final snapshot | Operator |
| Time-zone error | Medium when the candidate's zone is not the interviewer's | High | Every time shown to the user includes a zone; both clocks are in the slot view | Operator |
| Injected instruction in a note or in the FAQ | Medium as soon as free text is retrieved | High | Retrieved text is data. Injection calls cannot execute an effect above what the user asked. Poison document is a fixture | Operator |
| Over-trust in the agent | High if someone reads the demo as a model evaluation | High | README states the CI brain is a scripted provider. On 2026-10-17, `booking_end_to_end`, one model: n=5 PASS (about US$0.11) plus 3 PASS (US$0.054) was 8/8. VERIFY_REPORT_9 on HEAD `4c2170d` added PASS 3/3 at US$0.06728 (`usage.cost_in_usd_ticks`). Cumulative 11/11 PASS with a simulated approval. That does not prove the model retries the tool, because the runtime executes the approved call. Small sample, not a rate | Owner of the repo |
| Simulated recruiter approval | Certain in this repo: the scenario and the demo inject the decision | High if that injection is mistaken for a person | In production the approval has to arrive on an authenticated channel. This repo does not implement that channel. Offline adversarial check 2026-10-17: the human gate was not bypassed in 11 cases (small n) | Operator |
| Candidate PII in logs or traces | Medium if a real mailbox is copied into the trace | High | Emails minimized to `[email]` in the trace; secret-shaped strings redacted; ledger must not contain the API key | Operator |
| Cross-candidate mention the check misses | Medium if the model obfuscates | High for privacy, low on this fictional roster | `no_cross_candidate_access` matches a direct name, address, or id. It misses an obfuscated address, an address with spaces, and a first name alone. Offline on 2026-10-17: 6/6 direct leaks detected, 3 clean controls, small n | Operator |
| Telling the candidate the invite went out | High on the 2026-10-17 sample where the model said the email was approved and sent while outbox=0 | High | External check of the verb-and-object detector, before this verb expansion (VERIFY_REPORT_9, HEAD `4c2170d`, empty outbox, n=20, small): recall 15/20, false positives 1/20. After a real send, 0/20 of those claims were flagged. Recall after this expansion: not measured yet. An earlier different list, before that detector, was 2/14 caught and 0/9 false positives. Before the phrase list grew, another set was 9/14 with false positives 2/9 (`will be emailed`, `quedará en la bandeja de salida`) | Operator |

Not covered yet: a review of a real identity provider, a penetration test, and a data-processing agreement. Those are outside this lab.
