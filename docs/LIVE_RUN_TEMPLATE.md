# Live run template

No live run has been recorded. Real-model results: none yet.

Do not fill this table from the scripted eval. A row is valid only after `python3 -m scheduling_agent live --scenario <id> --max-turns 12` against an OpenAI-compatible endpoint, with `LIVE_LLM=1` and a spend cap.

| Date (UTC) | Model | Command | Scenarios (n) | Invariant pass/fail | Tokens in | Tokens out | Cost | Cost status | Ledger path |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |

Rules for a future row:

- Cost comes from `LLM_PRICE_IN_PER_MTOK` and `LLM_PRICE_OUT_PER_MTOK` in the environment of that run. If those were unset, write `unknown` and the `MAX_LIVE_TOKENS` value.
- Do not paste the API key, the raw ledger if it could contain one, or candidate data that is not synthetic.
- A pass is "invariants held", not "the prose looked right".
