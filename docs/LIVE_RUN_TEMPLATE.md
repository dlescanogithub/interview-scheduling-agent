# Live run template

Tercera verificación live, 2026-10-17: 3 corridas de `happy_path` con grok-4.20-0309-non-reasoning, comando `python3 -m scheduling_agent live --scenario happy_path --max-turns 12`. 0/3 agendaron. El usuario simulado dijo solo "Sí, confirmo." y el modelo repreguntó en vez de tomar el último slot. Las 3 corridas violaron `times_include_timezone` porque listaron horarios sin zona. Esas dos causas se corrigen en este PR (slot pendiente en el contexto, y un post-check que no muestra una hora sin offset). Re-verificación pendiente. Token counts and cost for those calls are not recorded here. Real-model results after the fix: none yet.

An earlier trio on the same date crashed twice on a naive datetime and once booked nothing with interviewer id `ana-luz`. That crash is already fixed on main. Do not treat an invariant pass without a booking as a completed task.

Do not fill this table from the scripted eval. A row is valid only after `python3 -m scheduling_agent live --scenario <id> --max-turns 12` against an OpenAI-compatible endpoint, with `LIVE_LLM=1` and a spend cap.

| Date (UTC) | Model | Command | Scenarios (n) | Invariant pass/fail | Tokens in | Tokens out | Cost | Cost status | Ledger path |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |  |  |

Rules for a future row:

- Cost comes from `LLM_PRICE_IN_PER_MTOK` and `LLM_PRICE_OUT_PER_MTOK` in the environment of that run. If those were unset, write `unknown` and the `MAX_LIVE_TOKENS` value.
- Do not paste the API key, the raw ledger if it could contain one, or candidate data that is not synthetic.
- A pass is "invariants held", not "the prose looked right".
