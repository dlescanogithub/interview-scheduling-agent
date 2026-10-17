# Risks

Qualitative labels only. No measured probabilities.

| Risk | Probability | Impact | Mitigation | Owner |
| --- | --- | --- | --- | --- |
| Wrong invite (right person, wrong slot, or the reverse) | Medium if a real mailbox is attached; low on the mock because the hash must match | High | User restatement, recruiter approval bound to the parameter hash, recall steps in the runbook | Recruiter |
| Double booking | Low while the calendar itself rejects overlaps; higher if a second writer bypasses it | High | Overlap check inside the calendar, including buffer; invariant on the final snapshot | Operator |
| Time-zone error | Medium when the candidate's zone is not the interviewer's | High | Every time shown to the user includes a zone; both clocks are in the slot view | Operator |
| Injected instruction in a note or in the FAQ | Medium as soon as free text is retrieved | High | Retrieved text is data. Injection calls cannot execute an effect above what the user asked. Poison document is a fixture | Operator |
| Over-trust in the agent | High if someone reads the demo as a model evaluation | High | README states the CI brain is a scripted provider. On 2026-10-17, `booking_end_to_end`, one model: 11/11 PASS, then VERIFY_REPORT_10 on HEAD `bb314c9` added PASS 3/3 at US$0.05378 (`usage.cost_in_usd_ticks`). Cumulative 14/14 PASS with a simulated approval. That does not prove the model retries the tool, because the runtime executes the approved call. Small sample, not a rate | Owner of the repo |
| Simulated recruiter approval | Certain in this repo: the scenario and the demo inject the decision | High if that injection is mistaken for a person | In production the approval has to arrive on an authenticated channel. This repo does not implement that channel. Offline adversarial check 2026-10-17: the human gate was not bypassed in 11 cases (small n) | Operator |
| Candidate PII in logs or traces | Medium if a real mailbox is copied into the trace | High | Emails minimized to `[email]` in the trace; secret-shaped strings redacted; ledger must not contain the API key | Operator |
| Cross-candidate mention the check misses | Medium if the model obfuscates | High for privacy, low on this fictional roster | `no_cross_candidate_access` matches a direct name, address, or id. It misses an obfuscated address, an address with spaces, and a first name alone. Offline on 2026-10-17: 6/6 direct leaks detected, 3 clean controls, small n | Operator |
| Telling the candidate the invite went out | High on the 2026-10-17 sample where the model said the email was approved and sent while outbox=0 | High | VERIFY_REPORT_10, new set, HEAD `bb314c9`, before this word-boundary fix (empty outbox, n=20, small, not conclusive): recall 15/20, false positives 1/20. After a real send, 0/20 of that set were flagged. Recall after this fix: not measured yet. VERIFY_REPORT_9, a different list before the verb expansion, was also 15/20 and 1/20; the two are not comparable. Before the verb-and-object detector: 2/14 caught and 0/9 false positives. Before the phrase list grew: 9/14 with false positives 2/9 (`will be emailed`, `quedará en la bandeja de salida`) | Operator |

Not covered yet: a review of a real identity provider, a penetration test, and a data-processing agreement. Those are outside this lab.
