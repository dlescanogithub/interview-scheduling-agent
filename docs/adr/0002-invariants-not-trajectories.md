# ADR 0002: Invariants, not exact trajectories

## Status

Accepted

## Context

Asserting the exact list of tool calls breaks as soon as the policy asks one extra clarifying question. The property we care about is whether a booking is double, unconfirmed, or emailed without the matching approval.

## Decision

Each scenario lists user turns and the invariants that must hold. `scheduling_agent.invariants` reads the trace. Allowed tools are a subset check. The eval does not compare the call sequence to a golden list.

The forced regression skips scenario expectations and runs `EagerProvider` with the gates bypassed, so the confirmation and approval invariants fail and the process exits 1.

## Consequences

A policy change that still books the confirmed slot keeps the gate green. A change that books without a yes, or sends without the hash, goes red even if the prose looks fine. Tests include one hand-built failing trace per invariant so a check cannot pass by never firing.
