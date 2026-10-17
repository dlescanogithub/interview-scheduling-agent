# Risks

Qualitative labels only. No measured probabilities.

| Risk | Probability | Impact | Mitigation | Owner |
| --- | --- | --- | --- | --- |
| Wrong invite (right person, wrong slot, or the reverse) | Medium if a real mailbox is attached; low on the mock because the hash must match | High | User restatement, recruiter approval bound to the parameter hash, recall steps in the runbook | Recruiter |
| Double booking | Low while the calendar itself rejects overlaps; higher if a second writer bypasses it | High | Overlap check inside the calendar, including buffer; invariant on the final snapshot | Operator |
| Time-zone error | Medium when the candidate's zone is not the interviewer's | High | Every time shown to the user includes a zone; both clocks are in the slot view | Operator |
| Injected instruction in a note or in the FAQ | Medium as soon as free text is retrieved | High | Retrieved text is data. Injection calls cannot execute an effect above what the user asked. Poison document is a fixture | Operator |
| Over-trust in the agent | High if someone reads the demo as a model evaluation | High | README states the CI brain is a scripted provider. The 2026-10-17 `booking_end_to_end` sample (n=6) scheduled 6/6 and had no legitimate PASS. An earlier `happy_path` check that day was INCOMPLETE 3/3 with 0 bookings | Owner of the repo |
| Candidate PII in logs or traces | Medium if a real mailbox is copied into the trace | High | Emails minimized to `[email]` in the trace; secret-shaped strings redacted; ledger must not contain the API key | Operator |

Not covered yet: a review of a real identity provider, a penetration test, and a data-processing agreement. Those are outside this lab.
