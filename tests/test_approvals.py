"""Approval rows are bound to the exact parameter hash."""

from __future__ import annotations

import pytest
from tests.support import make_ctx

from scheduling_agent.approvals import param_hash
from scheduling_agent.clock import FixedClock
from scheduling_agent.config import Settings

ARGS_A = {
    "booking_id": "book-a",
    "candidate_id": "cand-uno",
    "to": "candidata.uno@mail.example",
    "interviewer_id": "iv-ana",
    "start": "2026-04-14T12:00:00Z",
    "timezone": "America/Argentina/Buenos_Aires",
}
ARGS_B = {**ARGS_A, "start": "2026-04-14T13:00:00Z"}


def test_approving_invite_a_does_not_authorize_invite_b() -> None:
    ctx = make_ctx()
    row = ctx.approvals.request(
        approval_id="appr-1", tool="send_invite_email", args=ARGS_A
    )
    decided = ctx.approvals.decide(row.id, "approve")
    assert decided.status == "approved"
    assert ctx.approvals.matching("send_invite_email", ARGS_A) is not None
    assert ctx.approvals.matching("send_invite_email", ARGS_B) is None
    digest_a = param_hash("send_invite_email", ARGS_A)
    digest_b = param_hash("send_invite_email", ARGS_B)
    assert digest_a != digest_b


def test_expired_approval_does_not_match() -> None:
    settings = Settings(approval_ttl_seconds=30)
    ctx = make_ctx(settings)
    row = ctx.approvals.request(
        approval_id="appr-1", tool="send_invite_email", args=ARGS_A
    )
    ctx.approvals.decide(row.id, "approve")
    assert isinstance(ctx.clock, FixedClock)
    ctx.clock.advance(31)
    assert ctx.approvals.classify("send_invite_email", ARGS_A) is not None
    assert ctx.approvals.classify("send_invite_email", ARGS_A).status == "expired"  # type: ignore[union-attr]
    assert ctx.approvals.matching("send_invite_email", ARGS_A) is None


def test_rejection_is_not_retried_as_a_fresh_success() -> None:
    ctx = make_ctx()
    row = ctx.approvals.request(
        approval_id="appr-1", tool="send_invite_email", args=ARGS_A
    )
    rejected = ctx.approvals.decide(row.id, "reject")
    assert rejected.status == "rejected"
    again = ctx.approvals.request(
        approval_id="appr-2", tool="send_invite_email", args=ARGS_A
    )
    assert again.id == row.id
    assert again.status == "rejected"
    assert ctx.approvals.matching("send_invite_email", ARGS_A) is None
    assert ctx.approvals.latest_pending() is None


def test_decide_rejects_unknown_rows_and_bad_decisions() -> None:
    ctx = make_ctx()
    with pytest.raises(KeyError):
        ctx.approvals.decide("missing", "approve")
    row = ctx.approvals.request(
        approval_id="appr-1", tool="send_invite_email", args=ARGS_A
    )
    with pytest.raises(ValueError):
        ctx.approvals.decide(row.id, "maybe")
    assert isinstance(ctx.clock, FixedClock)
    ctx.clock.advance(ctx.settings.approval_ttl_seconds + 1)
    expired = ctx.approvals.decide(row.id, "approve")
    assert expired.status == "expired"
    assert "param_hash" in row.as_dict()
