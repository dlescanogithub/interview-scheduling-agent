# Discovery

Ten questions to ask before changing this lab into someone else's system. Each answer changes a design choice. The people and the company in this repo stay fictional.

1. **Which system is the calendar of record?** If it is an internal tool, the adapter is a small client behind the same `Calendar` operations. If it is a hosted calendar API, the book still has to fail closed on conflict. The gates do not move.
2. **Who may approve an external message?** Today that person is the recruiter. If the rule is "the candidate's yes is enough", the second gate is a product decision and this repo's default would be wrong for them. If two people must approve, the hash binding stays and the store gains a second decision.
3. **Which time zones are in play?** Interviewers here are in `America/Argentina/Buenos_Aires` and `UTC`. A candidate in another zone must see both clocks. A single-zone team can shorten the restatement, not skip the zone label.
4. **How many candidates per week?** The [EST] case uses 40 a month. A much higher volume means the hold TTL and the approval queue need an owner, or the human gate becomes a bottleneck. That is a reason to stay in shadow mode, not a reason to drop the gate.
5. **What accessibility needs are in scope?** Captions, a companion in the room, or a screen-reader path change the FAQ and the channel. They do not change the confirmation sentence. This repo has not been tested with assistive tech. That testing is design-only.
6. **How long may candidate data be kept?** A short retention window means the trace cannot keep the mailbox (it already replaces addresses with `[email]`) and the runbook needs a deletion step. A long window needs an owner and a place to store it. This lab keeps traces in memory for the run.
7. **What must the agent never do?** If the answer is "never email", the kill switch stays off. If the answer is "never reveal another candidate", the cross-candidate refusal stays even when a note in the FAQ says otherwise. Write the never-list before any live call.
8. **What is the reschedule and cancel rule?** The FAQ states a synthetic policy. A different notice period changes the copy and which external tool is allowed after cancel. The confirmation of the cancel stays.
9. **Which languages must the dialogue support?** The scripted policy covers Spanish and English. Another language needs new strings and new FAQ documents. Do not treat the BM25 hit rate as proof that a third language will work.
10. **Who owns a wrong invite after it would have left?** If the recruiter owns it, the recall procedure in the runbook is theirs. If a vendor owns delivery, the in-memory outbox is not an audit trail anymore and the design needs a real receipt. This repo does not have that receipt.
