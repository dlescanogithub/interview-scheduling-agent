"""Approval runs the stored call. A different hash, a reject, or silence does not."""

from __future__ import annotations

from tests.support import make_ctx

from scheduling_agent.agent import Agent
from scheduling_agent.cassette import CompletionRequest, CompletionResponse
from scheduling_agent.tools import execute_tool

EMAIL_A = {
    "booking_id": "book-a",
    "candidate_id": "cand-uno",
    "to": "candidata.uno@mail.example",
    "interviewer_id": "iv-ana",
    "start": "2026-04-14T12:00:00Z",
    "timezone": "America/Argentina/Buenos_Aires",
}
EMAIL_B = {**EMAIL_A, "start": "2026-04-14T13:00:00Z"}


class Quiet:
    """Talks. Never proposes a tool, so a retry cannot be what sends the mail."""

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        assert request.messages
        return CompletionResponse(text="Sigo en el chat.", purpose="talk")


def test_approval_executes_the_stored_param_hash() -> None:
    ctx = make_ctx()
    pending = execute_tool(ctx, "send_invite_email", EMAIL_A)
    assert pending["executed"] is False
    Agent(ctx, Quiet()).handle_recruiter("approve")
    assert len(ctx.outbox) == 1
    executed = [
        event.payload
        for event in ctx.trace.events
        if event.kind == "tool_result" and event.payload.get("executed") is True
    ]
    assert executed[-1]["name"] == "send_invite_email"
    assert executed[-1]["origin"] == "approval"
    assert executed[-1]["param_hash"] == pending["param_hash"]
    again = execute_tool(ctx, "send_invite_email", EMAIL_A)
    assert again["executed"] is False
    assert again["output"]["detail"] == "already_queued"
    assert len(ctx.outbox) == 1


def test_altered_params_do_not_execute_after_approval() -> None:
    ctx = make_ctx()
    pending = execute_tool(ctx, "send_invite_email", EMAIL_A)
    Agent(ctx, Quiet()).handle_recruiter("approve")
    other = execute_tool(ctx, "send_invite_email", EMAIL_B)
    assert other["status"] == "PENDING_APPROVAL"
    assert other["executed"] is False
    assert other["param_hash"] != pending["param_hash"]
    assert len(ctx.outbox) == 1
    assert "2026-04-14T12:00:00Z" in ctx.outbox[0].body
    assert "2026-04-14T13:00:00Z" not in ctx.outbox[0].body


def test_rejection_does_not_execute() -> None:
    ctx = make_ctx()
    execute_tool(ctx, "send_invite_email", EMAIL_A)
    Agent(ctx, Quiet()).handle_recruiter("reject")
    assert ctx.outbox == []
    executed = [
        event
        for event in ctx.trace.events
        if event.kind == "tool_result" and event.payload.get("executed") is True
    ]
    assert executed == []


def test_send_without_approval_does_not_execute() -> None:
    ctx = make_ctx()
    result = execute_tool(ctx, "send_invite_email", EMAIL_A)
    assert result["status"] == "PENDING_APPROVAL"
    assert result["executed"] is False
    assert ctx.outbox == []
