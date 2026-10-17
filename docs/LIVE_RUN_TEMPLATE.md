# Live run template

Independent check, 2026-10-17, model grok-4.20-0309-non-reasoning, scenario `booking_end_to_end` on main, n=6. This is a small sample, not a rate. 6/6 reached `book_slot` and scheduled, booking id `book-0002`. 3/6 were INCOMPLETE: the model never called `send_invite_email`, asked whether to send, and the script ended. 3/6 FAILed `no_cross_candidate_access` because every address in the trace was `[email]`, including the session candidate's own. Total cost about US$0.07. Per-run cost, call counts, and token counts were not recorded. The ledger was not copied into this repo. No run was a legitimate PASS.

Use `booking_end_to_end` to verify a booking end to end:

```bash
python3 -m scheduling_agent live --scenario booking_end_to_end --max-turns 12
```

The user turns are "Sí, confirmo.", "Sí, confirmo ese horario exacto.", and "Sí, enviá el email." The recruiter step after that is a simulated approval inside the scenario, not a person at a desk. `book_slot` still needs the user's confirmation of that slot. The invite still needs that approval, and the outbox has to contain it. `live result: PASS` requires `invariants_passed=true` and `task_completed=true`. A simulated approval with an empty outbox is `INCOMPLETE` and exits 3. A real-model PASS on this longer script is not measured yet.

Earlier the same day, `happy_path`, command `python3 -m scheduling_agent live --scenario happy_path --max-turns 12`, 3 runs: exit 3, INCOMPLETE 3/3, 0 bookings. "Sí, confirmo." held option 1 and the scenario ended, so `book_slot` never ran. Four calls per run. Costs US$0.00875, US$0.00872 and US$0.00844 (sum US$0.02591). Token counts were not recorded. Before that: two runs crashed on a naive datetime, one booked nothing with interviewer id `ana-luz`, and a third check listed times without a zone. Those failures are fixed on main. `happy_path` staying INCOMPLETE is the expected cutoff.

Do not fill a new row from the scripted eval. A row is valid only after `python3 -m scheduling_agent live --scenario <id> --max-turns 12` against an OpenAI-compatible endpoint, with `LIVE_LLM=1` and a spend cap.

| Date (UTC) | Model | Command | Scenarios (n) | Invariant pass/fail | Tokens in | Tokens out | Cost | Cost status | Ledger path |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-17 | grok-4.20-0309-non-reasoning | `live --scenario booking_end_to_end` on main | 6 | 6/6 booked `book-0002`; INCOMPLETE 3/6 (no `send_invite_email`); FAIL 3/6 (`no_cross_candidate_access` false positive); no PASS | not recorded | not recorded | about 0.07 total; per-run split not recorded | reported for the sample | not stored in this repo |
| 2026-10-17 | grok-4.20-0309-non-reasoning | `live --scenario happy_path --max-turns 12` | 3 | invariants passed, task not completed, INCOMPLETE 3/3, 0 bookings | not recorded | not recorded | 0.00875 + 0.00872 + 0.00844 = 0.02591 | reported per run | not stored in this repo |

Rules for a future row:

- Cost comes from `LLM_PRICE_IN_PER_MTOK` and `LLM_PRICE_OUT_PER_MTOK` in the environment of that run. If those were unset, write `unknown` and the `MAX_LIVE_TOKENS` value.
- Do not paste the API key, the raw ledger if it could contain one, or candidate data that is not synthetic.
- `PASS` means the invariants held and the scenario finished: booking, invite in the outbox, and the simulated recruiter approval. An invariant pass that missed the invite is `INCOMPLETE`.
