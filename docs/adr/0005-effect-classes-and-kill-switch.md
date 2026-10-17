# ADR 0005: Effect classes, kill switch, and cancel

## Status

Accepted

## Context

Some tools only read, some change the mock calendar in a way the same process can undo, and some would leave the building if they were real. Those three should not share one permission bit.

## Decision

The registry marks each tool `read`, `internal_reversible`, or `external`. External tools append to an in-memory outbox and nowhere else. `EXTERNAL_TOOLS_ENABLED=0` returns `KILL_SWITCH` before the bypass flag is consulted.

`cancel_booking` is `internal_reversible`. It is not in the original trio of hold, release, and book, because cancel and reschedule need a way to undo a mock booking without sending mail. `send_cancellation_notice` remains the external step.

## Consequences

A test can book and cancel inside the lab without an approval, and still cannot notify the candidate until the recruiter approves that notice. The kill switch is safe to flip during an incident without un-booking anyone by itself.
