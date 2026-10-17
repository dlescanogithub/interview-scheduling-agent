# ADR 0001: Scripted provider in CI

## Status

Accepted

## Context

A network call to a model makes CI slow, costly, and non-repeatable. It also invites a fake-versus-fake score to be read as model quality.

## Decision

CI and the default demo use `ScriptedProvider`, a deterministic policy over the transcript. `EagerProvider` exists only so `eval --regression` can show the gate fail. `InjectedProvider` exists so a poisoned note can be attempted and then blocked. The live adapter is off unless `LIVE_LLM=1` and is not a CI step.

## Consequences

The repo can test tools, gates, invariants, and the conversation flow. It cannot claim a model result. The README says so in the first lines. A future live run is judged with the same invariants and recorded in `docs/LIVE_RUN_TEMPLATE.md`.
