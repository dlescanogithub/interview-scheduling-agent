# Scope

No fees. No statement of work. Taller Aurora is fictional.

## Phases

| Phase | What happens | Status |
| --- | --- | --- |
| Shadow | The agent proposes slots. A person still sends every message and writes the real calendar. | Design only |
| Gate on the mock | Holds, user confirmation, recruiter approval, outbox, invariant gate. | Implemented |
| Real calendar and mailbox | Google-style or Microsoft-style APIs, with the same gates. | Design only |
| Other channels | WhatsApp or voice. | Design only |

## Assumptions

- Four interviewers, weekdays 09:00–17:00, 45-minute slots, 15-minute buffer.
- The session already knows which candidate is speaking. There is no login.
- External effects are the three outbox tools. `book_slot` and `cancel_booking` stay inside the mock and can be undone there.
- CI runs the scripted provider only. Live mode is off and is not a phase of this repo's default path.

## Out of scope

ATS, candidate authentication, embeddings, load tests, accessibility tests with people, payments, and any real customer data.

## Exit criteria for the implemented phase

- `python3 -m scheduling_agent eval` exits 0.
- `python3 -m scheduling_agent eval --regression` exits 1, and the failures include the approval invariant and the user-confirmation invariant.
- A hand-built trace can fail each invariant.
- `EXTERNAL_TOOLS_ENABLED=0` blocks external tools even when the regression bypass is on.

Those criteria are about the harness. They are not exit criteria for a production rollout.
