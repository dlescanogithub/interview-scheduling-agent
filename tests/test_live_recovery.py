"""Live tool mistakes stay inside the tool result. A fake transport, no socket."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.support import make_ctx
from tests.test_live import _settings

from scheduling_agent.agent import Agent
from scheduling_agent.cassette import CompletionRequest, CompletionResponse
from scheduling_agent.cli import live_outcome, render_live_result
from scheduling_agent.invariants import Violation
from scheduling_agent.live import LiveProvider, SpendLedger
from scheduling_agent.runner import (
    ScenarioResult,
    find_root,
    load_scenarios,
    run_scenario,
)
from scheduling_agent.tools import NAIVE_DATETIME_FIX, execute_tool

NAIVE_ARGS = {
    "interviewer_id": "iv-ana",
    "range_start": "2026-04-14T00:00:00",
    "range_end": "2026-04-14T23:00:00",
    "candidate_tz": "America/Argentina/Buenos_Aires",
}
UNKNOWN_ARGS = {
    "interviewer_id": "ana-luz",
    "range_start": "2026-04-14T12:00:00Z",
    "range_end": "2026-04-15T00:00:00Z",
    "candidate_tz": "America/Argentina/Buenos_Aires",
}
VALID_ARGS = {
    "interviewer_id": "iv-ana",
    "range_start": "2026-04-14T12:00:00Z",
    "range_end": "2026-04-15T00:00:00Z",
    "candidate_tz": "America/Argentina/Buenos_Aires",
}


def _call(name: str, arguments: dict[str, Any] | str, call_id: str) -> dict[str, Any]:
    encoded: dict[str, Any] | str = arguments
    return {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "function": {"name": name, "arguments": encoded},
                        }
                    ],
                }
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10},
    }


def _text(body: str) -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": body}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 8},
    }


class ScriptTransport:
    """Returns the next canned completion. Records every request body."""

    def __init__(self, steps: list[dict[str, Any]]) -> None:
        self.steps = steps
        self.bodies: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        self.bodies.append(body)
        assert url.endswith("/chat/completions")
        assert timeout == 60
        return self.steps[len(self.bodies) - 1]


def _tool_texts(body: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for message in body.get("messages", []):
        if isinstance(message, dict) and message.get("role") == "tool":
            found.append(str(message.get("content") or ""))
    return found


def test_naive_datetime_is_a_tool_error_not_a_crash() -> None:
    ctx = make_ctx()
    result = execute_tool(ctx, "list_availability", NAIVE_ARGS)
    assert result["executed"] is False
    assert result["status"] == "TOOL_ERROR"
    assert result["output"]["error"] == "naive_datetime"
    assert "2026-10-20T10:00:00-03:00" in result["output"]["how_to_fix"]
    assert result["output"]["how_to_fix"] == NAIVE_DATETIME_FIX
    assert ctx.calendar.holds == {}


def test_unknown_interviewer_names_the_real_ids() -> None:
    ctx = make_ctx()
    result = execute_tool(ctx, "list_availability", UNKNOWN_ARGS)
    assert result["executed"] is False
    assert result["status"] == "NOT_FOUND"
    assert "ana-luz" in result["output"]["detail"]
    fix = result["output"]["how_to_fix"]
    assert "iv-ana" in fix
    assert "Ana Luz" in fix
    assert "not an id" in fix


def test_fake_transport_recovers_after_naive_and_unknown_id(tmp_path: Path) -> None:
    steps = [
        _call("list_availability", json.dumps(NAIVE_ARGS), "call-naive"),
        _call("list_availability", json.dumps(UNKNOWN_ARGS), "call-unknown"),
        _call("list_availability", json.dumps(VALID_ARGS), "call-ok"),
        _text("I can offer times with Ana Luz. Reply yes to confirm."),
    ]
    transport = ScriptTransport(steps)
    ctx = make_ctx()
    provider = LiveProvider(
        _settings(),
        transport,
        SpendLedger(tmp_path / "ledger.jsonl"),
        clock=ctx.clock,
    )
    agent = Agent(ctx, provider)
    agent.handle_user("I want an interview with Ana Luz.")
    assert len(transport.bodies) == 4
    prompt = str(transport.bodies[0]["messages"][0]["content"])
    assert "America/Argentina/Buenos_Aires" in prompt
    assert "2026-04-13T09:00:00-03:00" in prompt
    assert "iv-ana (Ana Luz)" in prompt
    assert "09:00-17:00" in prompt
    assert "2026-10-20T10:00:00-03:00" in prompt
    first_fix = _tool_texts(transport.bodies[1])[-1]
    assert "naive_datetime" in first_fix
    assert "2026-10-20T10:00:00-03:00" in first_fix
    second_fix = _tool_texts(transport.bodies[2])[-1]
    assert "ana-luz" in second_fix
    assert "iv-ana" in second_fix
    recovered = _tool_texts(transport.bodies[3])[-1]
    parsed = json.loads(recovered)
    assert parsed["status"] == "OK"
    assert parsed["executed"] is True
    assert parsed["output"]["slots"]
    assert "sk-" not in json.dumps(transport.bodies)


def test_invalid_json_is_returned_to_the_model(tmp_path: Path) -> None:
    steps = [
        _call("list_availability", "{not-json", "call-bad"),
        _text("The argument was not JSON. I did not book anything."),
    ]
    transport = ScriptTransport(steps)
    ctx = make_ctx()
    provider = LiveProvider(
        _settings(),
        transport,
        SpendLedger(tmp_path / "ledger.jsonl"),
        clock=ctx.clock,
    )
    Agent(ctx, provider).handle_user("hello")
    echoed = _tool_texts(transport.bodies[1])[0]
    assert "invalid_json" in echoed
    assert "2026-10-20T10:00:00-03:00" in echoed


def test_empty_invariant_pass_is_not_pass() -> None:
    class Talk:
        def complete(self, request: CompletionRequest) -> CompletionResponse:
            return CompletionResponse(text="I did not book anything.", purpose="talk")

    root = find_root()
    scenario = next(
        item for item in load_scenarios(root / "scenarios") if item.id == "happy_path"
    )
    result = run_scenario(scenario, root=root, provider=Talk())
    label, code = live_outcome(result)
    rendered = render_live_result(result)
    assert result.violations == []
    assert result.booked == 0
    assert label == "INCOMPLETE"
    assert code == 3
    assert "live result: INCOMPLETE" in rendered
    assert "live result: PASS" not in rendered
    assert "live invariants: PASS" not in rendered


def test_invariant_failure_is_fail_not_incomplete() -> None:
    result = ScenarioResult(
        scenario_id="happy_path",
        violations=[Violation("no_double_booking", "overlap")],
        allowed_ok=True,
        expect_failures=["booked expected True got 0"],
        terminal="clarifying",
        outbox=0,
        booked=0,
        handoff=False,
        turns_to_booking=None,
        clarifications=0,
        trace=[],
        messages=[],
    )
    assert live_outcome(result) == ("FAIL", 1)
    assert "live result: PASS" not in render_live_result(result)


def test_prompt_round_trip_keeps_the_session_header() -> None:
    from scheduling_agent.agent import _system_prompt
    from scheduling_agent.dialogue import parse_session

    ctx = make_ctx()
    view = parse_session([{"role": "system", "content": _system_prompt(ctx)}])
    assert view.candidate_id == "cand-one"
    assert view.now.year == 2026
