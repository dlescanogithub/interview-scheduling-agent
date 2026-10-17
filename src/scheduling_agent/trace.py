"""JSONL run trace. One event per line: run_id, ts, kind, payload.

Payloads are minimized: secret patterns are redacted and email addresses are
replaced. The outbox, not the trace, keeps the synthetic recipient address.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from scheduling_agent.clock import Clock
from scheduling_agent.logging_setup import redact
from scheduling_agent.timeutil import isoformat_utc

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def minimize(value: Any) -> Any:
    """Drop secret-shaped text and full email addresses from a payload."""
    if isinstance(value, str):
        return redact(_EMAIL.sub("[email]", value))
    if isinstance(value, list):
        return [minimize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): minimize(item) for key, item in value.items()}
    return value


@dataclass
class TraceEvent:
    run_id: str
    ts: str
    kind: str
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "ts": self.ts,
            "kind": self.kind,
            "payload": self.payload,
        }


class Trace:
    def __init__(self, run_id: str, clock: Clock) -> None:
        self.run_id = run_id
        self.clock = clock
        self.events: list[TraceEvent] = []

    def add(self, kind: str, **payload: Any) -> TraceEvent:
        event = TraceEvent(
            run_id=self.run_id,
            ts=isoformat_utc(self.clock.now()),
            kind=kind,
            payload=minimize(payload),
        )
        self.events.append(event)
        return event

    def to_jsonl(self) -> str:
        return "".join(
            json.dumps(event.as_dict(), ensure_ascii=False) + "\n"
            for event in self.events
        )

    def kinds(self) -> list[str]:
        return [event.kind for event in self.events]
