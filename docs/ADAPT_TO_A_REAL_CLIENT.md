# Adapting this lab

Read [DISCOVERY.md](DISCOVERY.md) first. Do not point this process at a real calendar until the never-list, the approver, and the retention window are written down.

What can move as-is:

- The effect classes and the kill switch.
- Approval bound to a hash of the exact arguments, with an expiry.
- User confirmation of one restated slot before a booking.
- Invariants over the trace, including the forced regression that must fail.
- Redaction of secret-shaped strings and minimization of email addresses in the trace.

What has to be replaced, and is design-only today:

- The YAML calendar, with a client whose conflict check still happens in the store, not only in the prompt.
- The in-memory outbox, with a mailbox that can accept a recall. Until that exists, do not describe a send as done.
- The scripted provider, with a live model under the spend cap. Judge that run with the invariant table, not with a vibe.
- The FAQ labels. The current 30 queries were written with the documents. A real corpus needs labels the author of the documents did not also write, or the hit rate stays an upper bound on a toy set.

Keep the data synthetic until there is a place to put real candidate data and a person who owns deletion. This repository is not that place.
