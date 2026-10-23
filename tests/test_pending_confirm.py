"""Short confirmations, zoned replies, and an empty live run.

The transport is fake. Nothing here opens a socket or calls a model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from tests.support import make_ctx
from tests.test_live import _settings
from tests.test_live_recovery import ScriptTransport, _call, _text

from scheduling_agent.agent import Agent, _lacks_explicit_zone
from scheduling_agent.cassette import CompletionRequest, CompletionResponse
from scheduling_agent.cli import main
from scheduling_agent.dialogue import format_slot_line, render_pending_slot
from scheduling_agent.invariants import TIME_RE
from scheduling_agent.live import LiveProvider, SpendLedger
from scheduling_agent.tools import execute_tool

LIST_ARGS = {
    "interviewer_id": "iv-ana",
    "range_start": "2026-04-14T12:00:00Z",
    "range_end": "2026-04-15T00:00:00Z",
    "candidate_tz": "America/Argentina/Buenos_Aires",
}


def _slot() -> dict[str, Any]:
    listed = execute_tool(make_ctx(), "list_availability", LIST_ARGS)
    slots = listed["output"]["slots"]
    assert slots
    return slots[0]


def _provider(
    ctx: Any, steps: list[dict[str, Any]], tmp_path: Path
) -> tuple[Agent, ScriptTransport]:
    transport = ScriptTransport(steps)
    provider = LiveProvider(
        _settings(),
        transport,
        SpendLedger(tmp_path / "ledger.jsonl"),
        clock=ctx.clock,
    )
    return Agent(ctx, provider), transport


def test_numbered_slot_uses_art_offset() -> None:
    slot = _slot()
    line = format_slot_line(1, slot, "en")
    assert line.startswith("1) Tue 14/04 ")
    assert "(ART, UTC-3)" in line
    assert not _lacks_explicit_zone(line)
    assert "pending_slot: none" == render_pending_slot(None)
    pending = render_pending_slot(slot, 1)
    assert pending.startswith("pending_slot: interviewer_id=iv-ana ")
    assert "(ART, UTC-3)" in pending


def test_short_yes_books_the_pending_slot(tmp_path: Path) -> None:
    slot = _slot()
    line = format_slot_line(1, slot, "en").split(" | ", 1)[0]
    hold = {
        "interviewer_id": slot["interviewer_id"],
        "candidate_id": "cand-uno",
        "start": slot["start"],
        "end": slot["end"],
    }
    book = {"hold_id": "hold-0001", **hold}
    steps = [
        _call("list_availability", json.dumps(LIST_ARGS), "call-list"),
        _text(f"{line}\nReply yes to confirm option 1."),
        _call("hold_slot", json.dumps(hold), "call-hold"),
        _call("book_slot", json.dumps(book), "call-book"),
        _text("It is booked on the internal calendar. Approval is still missing."),
    ]
    ctx = make_ctx()
    agent, transport = _provider(ctx, steps, tmp_path)
    agent.handle_user("I want an interview with Ana Luz on April 14.")
    assert ctx.pending_slot is not None
    assert ctx.pending_slot["start"] == slot["start"]
    reply = agent.handle_user("Yes, I confirm.")
    prompt = str(transport.bodies[2]["messages"][0]["content"])
    assert f"pending_slot: interviewer_id=iv-ana start={slot['start']}" in prompt
    user_lines = [
        str(message.get("content") or "")
        for message in transport.bodies[2]["messages"]
        if message.get("role") == "user"
    ]
    assert "Yes, I confirm." in user_lines
    booked = json.loads(_tool_text(transport.bodies[4], "book_slot"))
    assert booked["status"] == "OK"
    assert booked["executed"] is True
    assert "Approval" in reply
    assert len(ctx.confirmations) == 1


def test_that_one_confirms_pending_slot_without_a_new_question(tmp_path: Path) -> None:
    slot = _slot()
    line = format_slot_line(1, slot, "en").split(" | ", 1)[0]
    steps = [
        _call("list_availability", json.dumps(LIST_ARGS), "call-list"),
        _text(line),
        _text("I am staying with that time. I did not book anything."),
    ]
    ctx = make_ctx()
    agent, transport = _provider(ctx, steps, tmp_path)
    agent.handle_user("I want an interview with Ana Luz.")
    agent.handle_user("that one")
    prompt = str(transport.bodies[2]["messages"][0]["content"])
    assert "pending_slot: interviewer_id=iv-ana" in prompt
    assert ctx.confirmations[0]["start"] == slot["start"]
    assert ctx.confirmations[0]["kind"] == "book"


def test_option_1_confirms_the_first_offered_slot(tmp_path: Path) -> None:
    slot = _slot()
    line = format_slot_line(1, slot, "en").split(" | ", 1)[0]
    steps = [
        _call("list_availability", json.dumps(LIST_ARGS), "call-list"),
        _text(line),
        _text("Noted. I did not book anything."),
    ]
    ctx = make_ctx()
    agent, _transport = _provider(ctx, steps, tmp_path)
    agent.handle_user("I want an interview with Ana Luz.")
    agent.handle_user("option 1")
    assert ctx.confirmations[0]["start"] == slot["start"]


def test_bare_time_is_rewritten_before_the_user_sees_it(tmp_path: Path) -> None:
    bare = "Tuesday at 10:00."
    fixed = "1) Tue 14/04 15:00 (ART, UTC-3). I did not book anything."
    steps = [_text(bare), _text(fixed)]
    ctx = make_ctx()
    agent, transport = _provider(ctx, steps, tmp_path)
    reply = agent.handle_user("Hello.")
    assert reply == fixed
    assert bare not in reply
    feedback = str(transport.bodies[1]["messages"][-1]["content"])
    assert "ART, UTC-3" in feedback
    shown = [
        str(event.payload["text"])
        for event in ctx.trace.events
        if event.kind == "assistant_message"
    ]
    assert shown == [fixed]
    for text in shown:
        assert TIME_RE.search(text) is None or not _lacks_explicit_zone(text)


def test_zone_rewrite_stops_after_two_tries(tmp_path: Path) -> None:
    bare = "Tomorrow at 10:00."
    steps = [_text(bare), _text(bare), _text(bare)]
    ctx = make_ctx()
    agent, _transport = _provider(ctx, steps, tmp_path)
    reply = agent.handle_user("Hello.")
    assert "10:00" not in reply
    assert "without its zone" in reply
    shown = [
        str(event.payload["text"])
        for event in ctx.trace.events
        if event.kind == "assistant_message"
    ]
    assert shown == [reply]


def test_cli_live_without_a_booking_exits_incomplete(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LIVE_LLM", "1")
    monkeypatch.setenv("MAX_LIVE_SPEND_USD", "1")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk" + "-" + "cassette" + "only")
    monkeypatch.setenv("LLM_MODEL", "lab-model")
    monkeypatch.setenv("MAX_LIVE_TOKENS", "1000")

    class DummyTransport:
        def post(self, *_args: object, **_kwargs: object) -> dict[str, Any]:
            raise AssertionError("live CLI test must not open a socket")

    class TalkProvider:
        def __init__(
            self, _settings: object, transport: object, _ledger: object
        ) -> None:
            assert isinstance(transport, DummyTransport)

        def complete(self, _request: CompletionRequest) -> CompletionResponse:
            return CompletionResponse(text="I did not book anything.", purpose="talk")

    monkeypatch.setattr("scheduling_agent.cli.UrllibTransport", DummyTransport)
    monkeypatch.setattr("scheduling_agent.cli.LiveProvider", TalkProvider)
    code = main(["live", "--scenario", "happy_path", "--max-turns", "12"])
    captured = capsys.readouterr()
    assert code == 3
    assert "invariants_passed=true" in captured.out
    assert "task_completed=false" in captured.out
    assert "live result: INCOMPLETE" in captured.out
    assert "live result: PASS" not in captured.out
    assert "live invariants: PASS" not in captured.out


def _tool_text(body: dict[str, Any], name: str) -> str:
    messages = body["messages"]
    for message in reversed(messages):
        if message.get("role") == "tool" and name in str(message.get("content")):
            return str(message["content"])
    raise AssertionError(name)
