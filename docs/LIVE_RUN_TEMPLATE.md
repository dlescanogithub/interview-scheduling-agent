# Live run template

Fourth live check, 2026-10-17, model grok-4.20-0309-non-reasoning, command `python3 -m scheduling_agent live --scenario happy_path --max-turns 12`, 3 runs. Each run exited 3 with `invariants_passed=true`, `task_completed=false`, `live result: INCOMPLETE`. 0 bookings. No crashes. Numbered slots included a zone in 3/3. "Sí, confirmo." stored `pending_slot`, called `hold_slot` on option 1, and asked for a second explicit confirmation. `happy_path` has only two user turns, so `book_slot` never ran. Four calls per run. Costs US$0.00875, US$0.00872 and US$0.00844. Sum US$0.02591, about US$0.026. Token counts were not recorded. The ledger was not copied into this repo.

Use `booking_end_to_end` to verify a booking end to end:

```bash
python3 -m scheduling_agent live --scenario booking_end_to_end --max-turns 12
```

That scenario adds a third user turn, "Sí, confirmo ese horario exacto.", then the recruiter approval. `book_slot` still needs the user's confirmation of that slot. The invite still needs the recruiter approval. `live result: PASS` requires `invariants_passed=true` and `task_completed=true` (the booking the scenario expects). Anything short of that is `INCOMPLETE` and exits 3. End-to-end booking on a real model is pendiente de re-verificación con el escenario nuevo.

Earlier the same day: two runs crashed on a naive datetime, one booked nothing with interviewer id `ana-luz`, and a third check listed times without a zone. Those failures are fixed on main. `happy_path` staying INCOMPLETE is the expected cutoff, not a crash.

Do not fill a new row from the scripted eval. A row is valid only after `python3 -m scheduling_agent live --scenario <id> --max-turns 12` against an OpenAI-compatible endpoint, with `LIVE_LLM=1` and a spend cap.

| Date (UTC) | Model | Command | Scenarios (n) | Invariant pass/fail | Tokens in | Tokens out | Cost | Cost status | Ledger path |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-17 | grok-4.20-0309-non-reasoning | `live --scenario happy_path --max-turns 12` | 3 | invariants passed, task not completed, INCOMPLETE 3/3, 0 bookings | not recorded | not recorded | 0.00875 + 0.00872 + 0.00844 = 0.02591 | reported per run | not stored in this repo |

Rules for a future row:

- Cost comes from `LLM_PRICE_IN_PER_MTOK` and `LLM_PRICE_OUT_PER_MTOK` in the environment of that run. If those were unset, write `unknown` and the `MAX_LIVE_TOKENS` value.
- Do not paste the API key, the raw ledger if it could contain one, or candidate data that is not synthetic.
- `PASS` means the invariants held and the scenario's booking finished. An invariant pass with no booking is `INCOMPLETE`.
