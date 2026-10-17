"""Per-run state shared by the agent, the tool gateway and the trace."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scheduling_agent.approvals import ApprovalStore
from scheduling_agent.calendar import Calendar
from scheduling_agent.clock import Clock
from scheduling_agent.config import Settings
from scheduling_agent.retrieval import BM25
from scheduling_agent.trace import Trace


class IdFactory:
    def __init__(self) -> None:
        self._n = 0

    def next(self, kind: str) -> str:
        self._n += 1
        return f"{kind}-{self._n:04d}"


@dataclass
class OutboxMessage:
    id: str
    kind: str
    to: str
    subject: str
    body: str
    approval_id: str
    param_hash: str
    booking_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "id": self.id,
            "kind": self.kind,
            "to": self.to,
            "subject": self.subject,
            "body": self.body,
            "approval_id": self.approval_id,
            "param_hash": self.param_hash,
            "booking_id": self.booking_id,
        }


@dataclass
class RunContext:
    run_id: str
    candidate_id: str
    candidate_name: str
    candidate_email: str
    candidate_tz: str
    lang: str
    clock: Clock
    calendar: Calendar
    approvals: ApprovalStore
    trace: Trace
    retriever: BM25
    settings: Settings
    ids: IdFactory = field(default_factory=IdFactory)
    outbox: list[OutboxMessage] = field(default_factory=list)
    confirmations: list[dict[str, str]] = field(default_factory=list)
    user_max_effect: str = "read"
    turns: int = 0
    tool_calls: int = 0
    tool_counts: dict[str, int] = field(default_factory=dict)
    cost_micro: int = 0
    terminal: str = "no_booking"
    protected_ids: list[str] = field(default_factory=list)
    protected_names: list[str] = field(default_factory=list)
    known_doc_ids: list[str] = field(default_factory=list)
    bypass_gates: bool = False
    external_enabled: bool = True
    advance_after_hold_seconds: int | None = None
    advance_fired: bool = False
    pending_action: str | None = None
    offered_slots: list[dict[str, Any]] = field(default_factory=list)
    pending_slot: dict[str, Any] | None = None
    pending_index: int = 1
    messages: list[dict[str, Any]] = field(default_factory=list)
