# Live run template

ejecutado 3 veces el 2026-10-17: 2 crashes (corregidos en este PR), 1 corrida sin booking; re-verificación pendiente.

Those three calls used grok-4.20-0309-non-reasoning on `python3 -m scheduling_agent live --scenario happy_path --max-turns 12`. Two runs died on an uncaught `ValueError: naive datetime: 2026-04-14T00:00:00`. The run that finished printed an invariant pass and booked nothing: the model used the interviewer id `ana-luz`, which is not on the roster. Token counts and cost for those calls are not recorded here. Do not treat that invariant pass as a completed task. Real-model results after the fix: none yet.

Do not fill this table from the scripted eval. A row is valid only after `python3 -m scheduling_agent live --scenario <id> --max-turns 12` against an OpenAI-compatible endpoint, with `LIVE_LLM=1` and a spend cap.

| Date (UTC) | Model | Command | Scenarios (n) | Invariant pass/fail | Tokens in | Tokens out | Cost | Cost status | Ledger path |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |

Rules for a future row:

- Cost comes from `LLM_PRICE_IN_PER_MTOK` and `LLM_PRICE_OUT_PER_MTOK` in the environment of that run. If those were unset, write `unknown` and the `MAX_LIVE_TOKENS` value.
- Do not paste the API key, the raw ledger if it could contain one, or candidate data that is not synthetic.
- A pass is "invariants held", not "the prose looked right".
