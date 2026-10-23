"""Tool gateway: schema, budgets, kill switch, and the two human gates."""

from __future__ import annotations

from dataclasses import replace

from tests.support import make_ctx

from scheduling_agent.approvals import slot_hash
from scheduling_agent.config import Settings
from scheduling_agent.tools import execute_tool

EMAIL_A = {
    "booking_id": "book-a",
    "candidate_id": "cand-one",
    "to": "candidate.one@mail.example",
    "interviewer_id": "iv-ana",
    "start": "2026-04-14T12:00:00Z",
    "timezone": "America/Argentina/Buenos_Aires",
}
EMAIL_B = {**EMAIL_A, "start": "2026-04-14T13:00:00Z"}


def test_schema_rejects_extra_fields_and_bad_types() -> None:
    ctx = make_ctx()
    extra = execute_tool(ctx, "search_faq", {"query": "reprogramar", "extra": True})
    assert extra["status"] == "VALIDATION_ERROR"
    assert extra["executed"] is False
    boolean = execute_tool(
        ctx,
        "list_availability",
        {
            "interviewer_id": "iv-ana",
            "range_start": "2026-04-14T12:00:00Z",
            "range_end": "2026-04-14T20:00:00Z",
            "candidate_tz": "America/Argentina/Buenos_Aires",
            "limit": True,
        },
    )
    assert boolean["status"] == "VALIDATION_ERROR"
    missing = execute_tool(ctx, "search_faq", {})
    assert "missing" in missing["output"]["detail"]
    unknown = execute_tool(ctx, "drop_table", {})
    assert unknown["status"] == "UNKNOWN_TOOL"


def test_budget_stops_the_call_before_it_counts_as_success() -> None:
    ctx = make_ctx(Settings(max_tool_calls=1, per_tool_cap=1))
    first = execute_tool(ctx, "search_faq", {"query": "privacidad"})
    assert first["executed"] is True
    second = execute_tool(ctx, "search_faq", {"query": "privacidad"})
    assert second["status"] == "BUDGET_EXCEEDED"
    assert second["executed"] is False
    assert ctx.tool_calls == 1


def test_kill_switch_beats_the_regression_bypass() -> None:
    ctx = make_ctx(Settings(bypass_gates=True, external_tools_enabled=False))
    ctx.bypass_gates = True
    ctx.external_enabled = False
    result = execute_tool(ctx, "send_invite_email", EMAIL_A)
    assert result["status"] == "KILL_SWITCH"
    assert result["executed"] is False
    assert ctx.outbox == []


def test_external_call_without_approval_executes_nothing() -> None:
    ctx = make_ctx()
    result = execute_tool(ctx, "send_invite_email", EMAIL_A)
    assert result["status"] == "PENDING_APPROVAL"
    assert result["executed"] is False
    assert ctx.outbox == []
    assert result["approval_id"]


def test_approved_hash_does_not_send_a_different_invite() -> None:
    ctx = make_ctx()
    pending = execute_tool(ctx, "send_invite_email", EMAIL_A)
    ctx.approvals.decide(pending["approval_id"], "approve")
    other = execute_tool(ctx, "send_invite_email", EMAIL_B)
    assert other["status"] == "PENDING_APPROVAL"
    assert other["executed"] is False
    same = execute_tool(ctx, "send_invite_email", EMAIL_A)
    assert same["executed"] is True
    assert len(ctx.outbox) == 1
    assert ctx.outbox[0].to == "candidate.one@mail.example"


def test_rejected_and_cross_candidate_calls_do_not_execute() -> None:
    ctx = make_ctx()
    pending = execute_tool(ctx, "send_invite_email", EMAIL_A)
    ctx.approvals.decide(pending["approval_id"], "reject")
    again = execute_tool(ctx, "send_invite_email", EMAIL_A)
    assert again["status"] == "REJECTED"
    assert again["executed"] is False
    other = execute_tool(ctx, "get_booking", {"candidate_id": "cand-two"})
    assert other["status"] == "REFUSED"
    assert other["executed"] is False
    wrong_to = {**EMAIL_B, "to": "candidate.two@mail.example"}
    wrong_inbox = execute_tool(ctx, "send_invite_email", wrong_to)
    assert wrong_inbox["status"] == "REFUSED"


def test_book_slot_needs_a_matching_confirmation() -> None:
    ctx = make_ctx()
    listed = execute_tool(
        ctx,
        "list_availability",
        {
            "interviewer_id": "iv-ana",
            "range_start": "2026-04-14T00:00:00Z",
            "range_end": "2026-04-16T00:00:00Z",
            "candidate_tz": "America/Argentina/Buenos_Aires",
        },
    )
    slot = listed["output"]["slots"][0]
    held = execute_tool(
        ctx,
        "hold_slot",
        {
            "interviewer_id": slot["interviewer_id"],
            "candidate_id": "cand-one",
            "start": slot["start"],
            "end": slot["end"],
        },
    )
    args = {
        "hold_id": held["output"]["hold_id"],
        "candidate_id": "cand-one",
        "interviewer_id": slot["interviewer_id"],
        "start": slot["start"],
        "end": slot["end"],
    }
    blocked = execute_tool(ctx, "book_slot", args)
    assert blocked["status"] == "NEEDS_CONFIRMATION"
    assert blocked["executed"] is False
    ctx.confirmations.append(
        {
            "kind": "book",
            "slot_hash": slot_hash(
                interviewer_id=slot["interviewer_id"],
                candidate_id="cand-one",
                start=slot["start"],
                end=slot["end"],
            ),
        }
    )
    booked = execute_tool(ctx, "book_slot", args)
    assert booked["executed"] is True
    assert ctx.calendar.active_bookings()


def test_cancel_needs_confirmation_and_release_works() -> None:
    ctx = make_ctx()
    start = "2026-04-15T15:00:00Z"
    end = "2026-04-15T15:45:00Z"
    held = execute_tool(
        ctx,
        "hold_slot",
        {
            "interviewer_id": "iv-elena",
            "candidate_id": "cand-one",
            "start": start,
            "end": end,
        },
    )
    released = execute_tool(
        ctx,
        "release_hold",
        {"hold_id": held["output"]["hold_id"], "candidate_id": "cand-one"},
    )
    assert released["executed"] is True
    ctx.calendar.force_book(
        booking_id="book-fixed",
        interviewer_id="iv-elena",
        candidate_id="cand-one",
        start=ctx.clock.now().replace(hour=16),
        end=ctx.clock.now().replace(hour=16, minute=45),
    )
    # The clock instant above may fall outside working hours; use a known free slot.
    ctx.calendar.bookings.clear()
    from scheduling_agent.timeutil import parse_iso

    ctx.calendar.force_book(
        booking_id="book-fixed",
        interviewer_id="iv-elena",
        candidate_id="cand-one",
        start=parse_iso(start),
        end=parse_iso(end),
    )
    blocked = execute_tool(
        ctx, "cancel_booking", {"booking_id": "book-fixed", "candidate_id": "cand-one"}
    )
    assert blocked["status"] == "NEEDS_CONFIRMATION"
    ctx.confirmations.append({"kind": "cancel", "booking_id": "book-fixed"})
    cancelled = execute_tool(
        ctx, "cancel_booking", {"booking_id": "book-fixed", "candidate_id": "cand-one"}
    )
    assert cancelled["executed"] is True
    found = execute_tool(ctx, "get_booking", {"candidate_id": "cand-one"})
    assert found["output"]["bookings"] == []


def test_settings_replace_keeps_external_flag() -> None:
    ctx = make_ctx(replace(Settings(), external_tools_enabled=True))
    assert ctx.external_enabled is True
