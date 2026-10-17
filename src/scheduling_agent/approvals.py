"""Recruiter approvals bound to a hash of the exact tool parameters."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from scheduling_agent.clock import Clock
from scheduling_agent.timeutil import to_canonical


def param_hash(tool: str, args: dict[str, Any]) -> str:
    """Stable hash of a tool name and its arguments."""
    blob = json.dumps(
        {"args": args, "tool": tool},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def slot_hash(
    *,
    interviewer_id: str,
    candidate_id: str,
    start: str,
    end: str,
) -> str:
    return param_hash(
        "slot",
        {
            "candidate_id": candidate_id,
            "end": end,
            "interviewer_id": interviewer_id,
            "start": start,
        },
    )


@dataclass
class Approval:
    id: str
    tool: str
    param_hash: str
    args: dict[str, Any]
    status: str
    created_at: datetime
    expires_at: datetime

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tool": self.tool,
            "param_hash": self.param_hash,
            "status": self.status,
            "created_at": to_canonical(self.created_at),
            "expires_at": to_canonical(self.expires_at),
        }


class ApprovalStore:
    def __init__(self, clock: Clock, ttl_seconds: int) -> None:
        self.clock = clock
        self.ttl_seconds = ttl_seconds
        self._rows: dict[str, Approval] = {}

    def request(self, *, approval_id: str, tool: str, args: dict[str, Any]) -> Approval:
        digest = param_hash(tool, args)
        for row in self._rows.values():
            if row.param_hash == digest and row.status in {"pending", "rejected"}:
                return row
        now = self.clock.now()
        row = Approval(
            id=approval_id,
            tool=tool,
            param_hash=digest,
            args=args,
            status="pending",
            created_at=now,
            expires_at=now + timedelta(seconds=self.ttl_seconds),
        )
        self._rows[row.id] = row
        return row

    def decide(self, approval_id: str, decision: str) -> Approval:
        row = self._rows.get(approval_id)
        if row is None:
            raise KeyError(approval_id)
        if decision not in {"approve", "reject"}:
            raise ValueError(decision)
        if row.expires_at <= self.clock.now():
            row.status = "expired"
            return row
        row.status = "approved" if decision == "approve" else "rejected"
        return row

    def classify(self, tool: str, args: dict[str, Any]) -> Approval | None:
        """Find the row for this exact call, expiring it when the clock says so."""
        digest = param_hash(tool, args)
        now = self.clock.now()
        for row in self._rows.values():
            if row.tool != tool or row.param_hash != digest:
                continue
            if row.status in {"pending", "approved"} and row.expires_at <= now:
                row.status = "expired"
            return row
        return None

    def matching(self, tool: str, args: dict[str, Any]) -> Approval | None:
        """Return an approved, unexpired row only when the hash matches."""
        digest = param_hash(tool, args)
        now = self.clock.now()
        for row in self._rows.values():
            if row.tool != tool or row.param_hash != digest:
                continue
            if row.status == "approved" and row.expires_at > now:
                return row
        return None

    def latest_pending(self) -> Approval | None:
        pending = [row for row in self._rows.values() if row.status == "pending"]
        if not pending:
            return None
        return sorted(pending, key=lambda row: row.created_at)[-1]

    def all(self) -> list[Approval]:
        return list(self._rows.values())
