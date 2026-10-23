# Security

This repository is a synthetic lab. It does not connect to a real calendar or a real inbox.

## Reporting

Use GitHub private vulnerability reporting. On the Security tab, choose "Report a vulnerability". You can also contact the owner listed in `.github/CODEOWNERS`. Do not open a public issue that includes a credential, a trace, or a live ledger.

## Secrets

- Configuration comes from the environment. `.env` is git-ignored.
- Do not commit keys, tokens, or live ledgers (`var/` is git-ignored).
- `python -m scheduling_agent.secretscan` and the CI secret-scan step look for common credential shapes.
- Logs and traces pass through the same patterns. A live API key must not appear in a log line, an exception message, or the JSONL ledger.

## Controls that exist in this repo

- External tools (`send_invite_email`, `send_reschedule_email`, `send_cancellation_notice`) write only to an in-memory outbox, and only after a recruiter approval whose parameter hash matches the call.
- `EXTERNAL_TOOLS_ENABLED=0` is a kill switch. While it is off, external tools execute nothing. The regression bypass does not override it.
- `book_slot` requires an explicit user confirmation of the same slot, unless the process is the deliberate regression mode (`eval --regression`).
- Live mode refuses to start without `LIVE_LLM=1` and a `MAX_LIVE_SPEND_USD` greater than zero.

## Known limits

There is no authentication of candidates, no real transport security review, and no penetration test. See `docs/RISKS.md` and `docs/RUNBOOK.md`.

Live mode on the 2026-10-22 documentation revision is UNVERIFIED. No live provider call was made for that revision. The last recorded live sample is 2026-10-17, on earlier commits, and is summarized in the README. The recruiter approval in this repo is simulated. A real deployment would need it on an authenticated channel, and this repo does not implement that channel.
