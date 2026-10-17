# Cost

No vendor price list is stored in this repo. Simulated prices default to 0, so the scripted path costs 0 by construction. That 0 is not a market price.

Latency columns are **not measured**. The lab clock is injected and must not be reported as latency.

| Scenario | Model / provider | Tokens or units | Cost / run | p50 latency | p95 latency | Quality | Price date / source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CI eval, 25 scripted scenarios | Scripted fake provider | not a model call | 0 (SIM_PRICE_* default 0) | not measured | not measured | 25/25 invariant pass, simulated | simulated, 2026-10-17, commit `b684187e418dc0bd230117841ff8f6b4a6559fd2` |
| Forced regression | EagerProvider fake | not a model call | 0 | not measured | not measured | exit 1, by design | simulated, same commit |
| Live `happy_path`, 3 runs on 2026-10-17 | grok-4.20-0309-non-reasoning | 4 calls each; token counts not recorded | US$0.00875, US$0.00872, US$0.00844; sum US$0.02591 | not measured | not measured | INCOMPLETE 3/3, 0 bookings, invariants passed | reported for that run; not a stored vendor price list |
| Live `booking_end_to_end`, 3 more runs on 2026-10-17, after the approved-send change | grok-4.20-0309-non-reasoning | call counts not recorded; token counts not recorded | US$0.054 total; per-run split not recorded | not measured | not measured | PASS 3/3. With the n=5 row, 8/8 PASS with a simulated approval. One model, small sample, not a rate. Does not prove the model retries the tool | independent check that day; not a stored vendor price list |
| Live `booking_end_to_end`, n=5 on 2026-10-17, after the approved-send change | grok-4.20-0309-non-reasoning | call counts not recorded; token counts not recorded | about US$0.11 total; per-run split not recorded | not measured | not measured | 5/5 PASS with a simulated approval; outbox=1, origin=approval, same param_hash. Does not prove the model retries the tool. One model, small sample, not a rate | independent check that day; not a stored vendor price list |
| Live `booking_end_to_end`, n=8 on 2026-10-17 | grok-4.20-0309-non-reasoning | call counts not recorded; token counts not recorded | about US$0.15 total; per-run split not recorded | not measured | not measured | 0/8 PASS, 8/8 INCOMPLETE, 0 FAIL, outbox=0 after `PENDING_APPROVAL` with no retry. Small sample, not a rate | independent check that day; not a stored vendor price list |
| Live `booking_end_to_end`, n=6 on 2026-10-17 | grok-4.20-0309-non-reasoning | call counts not recorded; token counts not recorded | about US$0.07 total; per-run split not recorded | not measured | not measured | 6/6 booked `book-0002`; 3 INCOMPLETE without `send_invite_email`; 3 FAIL on a cross-candidate false positive; no PASS. Small sample, not a rate | independent check that day; not a stored vendor price list |

A live run refuses to start when `MAX_LIVE_SPEND_USD` is missing or not greater than 0. CI does not run live mode.
