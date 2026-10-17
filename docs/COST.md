# Cost

No vendor price list is stored in this repo. Simulated prices default to 0, so the scripted path costs 0 by construction. That 0 is not a market price.

Latency columns are **not measured**. The lab clock is injected and must not be reported as latency.

| Scenario | Model / provider | Tokens or units | Cost / run | p50 latency | p95 latency | Quality | Price date / source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CI eval, 25 scripted scenarios | Scripted fake provider | not a model call | 0 (SIM_PRICE_* default 0) | not measured | not measured | 25/25 invariant pass, simulated | simulated, 2026-10-17, commit `b684187e418dc0bd230117841ff8f6b4a6559fd2` |
| Forced regression | EagerProvider fake | not a model call | 0 | not measured | not measured | exit 1, by design | simulated, same commit |
| Live chat-completions | whatever `LLM_MODEL` names | ledger row after a real call | not measured | not measured | not measured | not measured | prices only from `LLM_PRICE_IN_PER_MTOK` and `LLM_PRICE_OUT_PER_MTOK` at run time; if unset, cost status is `unknown` when `MAX_LIVE_TOKENS` is set |

A live run refuses to start when `MAX_LIVE_SPEND_USD` is missing or not greater than 0. CI does not run live mode.
