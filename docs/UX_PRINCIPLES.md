# UX principles

The person in the session should always know what is proposed, what is booked, and what a human still has to do.

| Principle | How it shows up | Enforced? |
| --- | --- | --- |
| One question at a time | Ambiguous Tuesday asks which Tuesday. The next step waits. | Scripted policy |
| Restate the slot | Date, weekday, local time, and zone before a yes. | Invariant `times_include_timezone` on assistant text that contains a clock time |
| At most three options | The calendar limit is 3 and a fourth numbered option fails the invariant | `at_most_three_options` |
| Explicit yes | The proposal says to reply yes. `book_slot` checks a confirmation of that same slot | `book_preceded_by_user_confirmation` |
| Easy change or cancel | The person can pick another option, refuse, or cancel an existing booking after a confirmation | Scenarios `user_changes_mind`, `cancel`, `user_refuses_confirmation` |
| Say what happens next | After the yes, the text says a recruiter will approve the email and where it would go | Scripted copy |
| No internal jargon in the reply | The person hears slots and approval, not effect classes | Copy review; not a machine check |
| A person is always available | "Quiero una persona" and the failure paths hand off | Scenario `explicit_handoff` and the handoff metric |
| Accessibility | The FAQ mentions captions, a companion, and remote access. That is copy, not a test with assistive technology | Design-only beyond the FAQ |

Metrics on these flows are simulated-user metrics. See [METRICS.md](METRICS.md).
