# ADR 0003: Two confirmations

## Status

Accepted

## Context

The candidate and the recruiter are not the same approver. A yes to "Tuesday at 10:00" is not permission to email a different slot, and a recruiter's approval of one payload is not permission to send another.

## Decision

1. `book_slot` runs only after a user confirmation whose slot hash matches the interviewer, candidate, start, and end. `cancel_booking` runs only after a cancel or reschedule confirmation of that booking id.
2. An external tool runs only after a recruiter approval whose parameter hash matches the tool name and arguments, and only before that approval expires. Calling it early returns `PENDING_APPROVAL` and executes nothing. A rejection is sticky for that hash: the store does not open a fresh pending row for the same call.

Regression mode can bypass both gates. The kill switch cannot be bypassed.

## Consequences

The trace has to carry the confirmation and the approval decision, because the invariants read the trace rather than the provider's memory. Approving "invite A" in a test must not send "invite B".
