# 0007. Pending slot and zoned times

## Status

Accepted

## Context

On 2026-10-17 a third live check ran `happy_path` three times. None of them booked. The simulated user said only "Sí, confirmo." and the model asked again. All three runs violated `times_include_timezone` because the listed times had no zone.

## Decision

Offer at most three numbered slots in one form: `1) mar 20/10 10:00 (ART, UTC-3)`. Store the offered slot on the run as `pending_slot` and repeat that line in the system prompt. A short confirmation accepts that slot and is not asked again.

If a reply contains a clock time and is missing a zone or a numeric offset, do not show it. Send the model a rewrite instruction, at most twice, and then a sentence that contains no clock time.

## Consequences

The scripted proposals use the same line, so a bare yes still matches the slot that was shown. A live run that stays inside the invariants but never books is `INCOMPLETE` and exits 3. A fourth live check the same day (`happy_path`, 3 runs) showed numbered slots with a zone in 3/3 and the second-confirmation ask. A later `booking_end_to_end` sample that day did book; its PASS result is recorded in the live template, not in this decision.
