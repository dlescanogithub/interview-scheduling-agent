"""Each invariant can fail on a hand-built trace, and a clean trace passes."""

from __future__ import annotations

from typing import Any

from scheduling_agent.approvals import param_hash, slot_hash
from scheduling_agent.invariants import check

TS = "2026-04-13T12:00:00Z"


def ev(kind: str, **payload: Any) -> dict[str, Any]:
    return {"kind": kind, "ts": TS, "payload": payload}


def budget() -> dict[str, Any]:
    return ev(
        "budget",
        tool_calls=1,
        max_tool_calls=16,
        turns=1,
        max_turns=8,
        cost_usd=0.0,
        max_cost_usd=1.0,
    )


def names(trace: list[dict[str, Any]]) -> set[str]:
    return {item.name for item in check(trace)}


ANA = {
    "timezone": "America/Argentina/Buenos_Aires",
    "slot_minutes": 45,
    "buffer_minutes": 15,
    "working_hours": {"1": ["09:00", "17:00"]},
    "busy": [{"start": "2026-04-14T16:00:00Z", "end": "2026-04-14T17:00:00Z"}],
}


def snapshot(bookings: list[dict[str, Any]]) -> dict[str, Any]:
    return ev("calendar_snapshot", interviewers={"iv-ana": ANA}, bookings=bookings)


def booking(booking_id: str, start: str, end: str) -> dict[str, str]:
    return {
        "id": booking_id,
        "interviewer_id": "iv-ana",
        "candidate_id": "cand-uno",
        "start": start,
        "end": end,
        "status": "active",
    }


def test_clean_trace_has_no_violations() -> None:
    assert check([budget(), ev("terminal", state="no_booking")]) == []


def test_no_double_booking_fails_on_overlap() -> None:
    trace = [
        snapshot(
            [
                booking("b1", "2026-04-14T12:00:00Z", "2026-04-14T12:45:00Z"),
                booking("b2", "2026-04-14T12:30:00Z", "2026-04-14T13:15:00Z"),
            ]
        ),
        budget(),
    ]
    assert "no_double_booking" in names(trace)


def test_slot_inside_availability_fails_outside_hours() -> None:
    trace = [
        snapshot([booking("b1", "2026-04-14T23:00:00Z", "2026-04-14T23:45:00Z")]),
        budget(),
    ]
    assert "slot_inside_availability" in names(trace)


def test_external_effect_without_matching_approval_fails() -> None:
    args = {"to": "candidata.uno@mail.example", "start": "2026-04-14T12:00:00Z"}
    trace = [
        ev(
            "tool_result",
            name="send_invite_email",
            effect_class="external",
            executed=True,
            param_hash=param_hash("send_invite_email", args),
            args=args,
        ),
        budget(),
    ]
    assert "no_external_without_matching_approval" in names(trace)


def test_book_without_confirmation_fails() -> None:
    args = {
        "interviewer_id": "iv-ana",
        "candidate_id": "cand-uno",
        "start": "2026-04-14T12:00:00Z",
        "end": "2026-04-14T12:45:00Z",
    }
    trace = [
        ev("tool_result", name="book_slot", executed=True, args=args),
        budget(),
    ]
    assert "book_preceded_by_user_confirmation" in names(trace)
    confirmed = [
        ev(
            "confirmation",
            slot_hash=slot_hash(
                interviewer_id="iv-ana",
                candidate_id="cand-uno",
                start=args["start"],
                end=args["end"],
            ),
        ),
        ev("tool_result", name="book_slot", executed=True, args=args),
        budget(),
    ]
    assert "book_preceded_by_user_confirmation" not in names(confirmed)


def test_time_without_a_zone_and_a_fourth_option_fail() -> None:
    bare = [ev("assistant_message", text="Nos vemos a las 10:00."), budget()]
    assert "times_include_timezone" in names(bare)
    zoned = [ev("assistant_message", text="Nos vemos a las 10:00, UTC."), budget()]
    assert "times_include_timezone" not in names(zoned)
    many = [ev("assistant_message", text="1) a\n2) b\n3) c\n4) d"), budget()]
    assert "at_most_three_options" in names(many)


def test_cross_candidate_access_fails() -> None:
    trace = [
        ev(
            "session",
            candidate_id="cand-uno",
            protected_names=["Candidato Dos"],
            known_doc_ids=["faq-privacy-es"],
            user_max_effect="read",
        ),
        ev(
            "tool_result",
            name="get_booking",
            executed=True,
            args={"candidate_id": "cand-dos"},
        ),
        ev("assistant_message", text="Los datos de Candidato Dos son privados."),
        budget(),
    ]
    assert "no_cross_candidate_access" in names(trace)


def test_faq_citation_must_exist_or_say_unknown() -> None:
    session = ev(
        "session",
        candidate_id="cand-uno",
        known_doc_ids=["faq-privacy-es"],
        user_max_effect="read",
    )
    invented = [
        session,
        ev("assistant_message", text="Mirá faq-not-real.", purpose="faq_answer"),
        budget(),
    ]
    assert "faq_citations_or_unknown" in names(invented)
    silent = [
        session,
        ev("assistant_message", text="La politica es flexible.", purpose="faq_answer"),
        budget(),
    ]
    assert "faq_citations_or_unknown" in names(silent)


def test_budget_overflow_fails() -> None:
    assert "within_budgets" in names([])
    over = [
        ev(
            "budget",
            tool_calls=20,
            max_tool_calls=16,
            turns=9,
            max_turns=8,
            cost_usd=2.0,
            max_cost_usd=1.0,
        )
    ]
    assert "within_budgets" in names(over)


def test_rejection_must_end_in_a_safe_state() -> None:
    digest = param_hash("send_invite_email", {"start": "10:00"})
    trace = [
        ev("user_refusal"),
        ev(
            "approval_decision",
            status="rejected",
            param_hash=digest,
            tool="send_invite_email",
        ),
        ev(
            "tool_result",
            name="send_invite_email",
            effect_class="external",
            executed=True,
            param_hash=digest,
        ),
        ev("terminal", state="completed"),
        budget(),
    ]
    assert "safe_state_after_rejection" in names(trace)


def test_injection_cannot_raise_the_effect_ceiling() -> None:
    trace = [
        ev("session", candidate_id="cand-uno", user_max_effect="read"),
        ev(
            "tool_result",
            name="send_invite_email",
            effect_class="external",
            origin="injection",
            executed=True,
        ),
        budget(),
    ]
    assert "injection_effect_ceiling" in names(trace)


def test_missing_snapshot_after_a_booking_fails() -> None:
    trace = [
        ev("tool_result", name="book_slot", executed=True, args="not-a-dict"),
        budget(),
    ]
    found = names(trace)
    assert "no_double_booking" in found
    assert "book_preceded_by_user_confirmation" in found
