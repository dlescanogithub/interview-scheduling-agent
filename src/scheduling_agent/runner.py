"""Load scenarios and run them against the mock calendar."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from scheduling_agent.agent import Agent
from scheduling_agent.approvals import ApprovalStore
from scheduling_agent.calendar import CalendarError, load_calendar
from scheduling_agent.clock import FixedClock
from scheduling_agent.config import Settings
from scheduling_agent.invariants import Violation, check
from scheduling_agent.policy import ScriptedProvider
from scheduling_agent.providers import EagerProvider, FailNProvider, InjectedProvider
from scheduling_agent.retrieval import BM25, load_documents
from scheduling_agent.roster import CANDIDATES, other_markers
from scheduling_agent.runtime import RunContext
from scheduling_agent.timeutil import parse_iso
from scheduling_agent.trace import Trace


@dataclass
class Scenario:
    id: str
    description: str
    candidate_id: str
    lang: str
    provider: str
    allowed_tools: list[str]
    steps: list[dict[str, str]]
    fail_provider_times: int = 0
    external_enabled: bool = True
    advance_after_hold_seconds: int | None = None
    steal_proposed_slot: bool = False
    fixture_bookings: list[dict[str, str]] = field(default_factory=list)
    expect: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioResult:
    scenario_id: str
    violations: list[Violation]
    allowed_ok: bool
    expect_failures: list[str]
    terminal: str
    outbox: int
    booked: int
    handoff: bool
    turns_to_booking: int | None
    clarifications: int
    trace: list[dict[str, Any]]
    messages: list[dict[str, Any]]


def find_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "scenarios").is_dir() and (candidate / "data" / "faq").is_dir():
            return candidate
    return current


def load_scenarios(directory: Path) -> list[Scenario]:
    scenarios: list[Scenario] = []
    for path in sorted(directory.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"{path} is not a mapping")
        steps = raw.get("steps", [])
        bookings = raw.get("fixture_bookings", [])
        if not isinstance(steps, list) or not isinstance(bookings, list):
            raise ValueError(f"{path} has a bad steps or bookings list")
        expect = raw.get("expect", {})
        scenarios.append(
            Scenario(
                id=str(raw["id"]),
                description=str(raw.get("description", "")),
                candidate_id=str(raw.get("candidate_id", "cand-uno")),
                lang=str(raw.get("lang", "es")),
                provider=str(raw.get("provider", "scripted")),
                allowed_tools=[str(item) for item in raw.get("allowed_tools", [])],
                steps=[_step(item) for item in steps],
                fail_provider_times=int(raw.get("fail_provider_times", 0)),
                external_enabled=bool(raw.get("external_enabled", True)),
                advance_after_hold_seconds=(
                    int(raw["advance_after_hold_seconds"])
                    if raw.get("advance_after_hold_seconds") is not None
                    else None
                ),
                steal_proposed_slot=bool(raw.get("steal_proposed_slot", False)),
                fixture_bookings=[_booking(item) for item in bookings],
                expect=expect if isinstance(expect, dict) else {},
            )
        )
    return scenarios


def _step(item: object) -> dict[str, str]:
    if not isinstance(item, dict):
        raise ValueError("step must be a mapping")
    return {str(key): str(value) for key, value in item.items()}


def _booking(item: object) -> dict[str, str]:
    if not isinstance(item, dict):
        raise ValueError("fixture booking must be a mapping")
    return {str(key): str(value) for key, value in item.items()}


def _provider_for(scenario: Scenario, regression: bool) -> Any:
    if regression:
        return EagerProvider()
    if scenario.provider == "injected":
        inner = ScriptedProvider()
        return InjectedProvider(inner)
    scripted = ScriptedProvider()
    if scenario.fail_provider_times:
        return FailNProvider(scripted, scenario.fail_provider_times)
    return scripted


def run_scenario(
    scenario: Scenario,
    *,
    root: Path,
    settings: Settings | None = None,
    regression: bool = False,
    provider: Any | None = None,
) -> ScenarioResult:
    active = settings if settings is not None else Settings()
    if regression:
        active = Settings(
            max_turns=active.max_turns,
            max_tool_calls=active.max_tool_calls,
            per_tool_cap=active.per_tool_cap,
            max_cost_usd=active.max_cost_usd,
            sim_price_in_per_mtok=active.sim_price_in_per_mtok,
            sim_price_out_per_mtok=active.sim_price_out_per_mtok,
            hold_ttl_seconds=active.hold_ttl_seconds,
            approval_ttl_seconds=active.approval_ttl_seconds,
            retry_attempts=active.retry_attempts,
            retry_base_seconds=active.retry_base_seconds,
            retry_cap_seconds=active.retry_cap_seconds,
            external_tools_enabled=active.external_tools_enabled,
            bypass_gates=True,
            retrieval_threshold=active.retrieval_threshold,
            now_iso=active.now_iso,
        )
    clock = FixedClock(parse_iso(active.now_iso))
    calendar = load_calendar(root / "data" / "calendar" / "taller_aurora.yaml", clock)
    for booking in scenario.fixture_bookings:
        calendar.force_book(
            booking_id=booking["id"],
            interviewer_id=booking["interviewer_id"],
            candidate_id=booking["candidate_id"],
            start=parse_iso(booking["start"]),
            end=parse_iso(booking["end"]),
        )
    candidate = calendar.candidates[scenario.candidate_id]
    documents = load_documents(root / "data" / "faq")
    retriever = BM25(documents)
    ctx = RunContext(
        run_id=f"run-{scenario.id}",
        candidate_id=candidate.id,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        candidate_tz=candidate.timezone,
        lang=scenario.lang,
        clock=clock,
        calendar=calendar,
        approvals=ApprovalStore(clock, active.approval_ttl_seconds),
        trace=Trace(f"run-{scenario.id}", clock),
        retriever=retriever,
        settings=active,
        protected_ids=[key for key in CANDIDATES if key != candidate.id],
        protected_names=list(other_markers(candidate.id)),
        known_doc_ids=[document.id for document in documents],
        bypass_gates=active.bypass_gates,
        external_enabled=scenario.external_enabled and active.external_tools_enabled,
        advance_after_hold_seconds=None
        if regression
        else scenario.advance_after_hold_seconds,
    )
    chosen = provider if provider is not None else _provider_for(scenario, regression)
    agent = Agent(ctx, chosen)
    stolen = False
    for step in scenario.steps:
        role = step.get("role", "user")
        if role == "recruiter":
            agent.handle_recruiter(step.get("decision", "approve"))
        else:
            agent.handle_user(step.get("text", ""))
        if scenario.steal_proposed_slot and not stolen and not regression:
            stolen = _steal_first_slot(ctx)
    agent.finalize()
    trace = [event.as_dict() for event in ctx.trace.events]
    violations = check(trace)
    used = {
        str(event["payload"].get("name"))
        for event in trace
        if event.get("kind") == "tool_result" and isinstance(event.get("payload"), dict)
    }
    allowed_ok = used <= set(scenario.allowed_tools)
    booked = len(calendar.bookings_for(candidate.id))
    expect_failures = [] if regression else _expects(scenario.expect, ctx, booked)
    return ScenarioResult(
        scenario_id=scenario.id,
        violations=violations,
        allowed_ok=allowed_ok,
        expect_failures=expect_failures,
        terminal=ctx.terminal,
        outbox=len(ctx.outbox),
        booked=booked,
        handoff=ctx.terminal == "handoff"
        or any(event["kind"] == "handoff" for event in trace),
        turns_to_booking=_turns_to_booking(trace),
        clarifications=_clarifications(trace),
        trace=trace,
        messages=ctx.messages,
    )


def _steal_first_slot(ctx: RunContext) -> bool:
    from scheduling_agent.dialogue import latest_slots

    slots = latest_slots(ctx.messages)
    if not slots:
        return False
    slot = slots[0]
    try:
        ctx.calendar.force_book(
            booking_id=ctx.ids.next("race"),
            interviewer_id=str(slot["interviewer_id"]),
            candidate_id="cand-dos",
            start=parse_iso(str(slot["start"])),
            end=parse_iso(str(slot["end"])),
        )
    except CalendarError:
        return False
    return True


def _expects(expect: dict[str, Any], ctx: RunContext, booked: int) -> list[str]:
    failures: list[str] = []
    if "booked" in expect and bool(expect["booked"]) != (booked > 0):
        failures.append(f"booked expected {expect['booked']} got {booked}")
    if "outbox_min" in expect and len(ctx.outbox) < int(expect["outbox_min"]):
        failures.append(f"outbox {len(ctx.outbox)} < {expect['outbox_min']}")
    if "outbox_max" in expect and len(ctx.outbox) > int(expect["outbox_max"]):
        failures.append(f"outbox {len(ctx.outbox)} > {expect['outbox_max']}")
    terminal_in = expect.get("terminal_in")
    if isinstance(terminal_in, list) and ctx.terminal not in [
        str(item) for item in terminal_in
    ]:
        failures.append(f"terminal {ctx.terminal} not in {terminal_in}")
    if "handoff" in expect and bool(expect["handoff"]) != (ctx.terminal == "handoff"):
        failures.append(f"handoff expected {expect['handoff']}")
    return failures


def _turns_to_booking(trace: list[dict[str, Any]]) -> int | None:
    users = 0
    for event in trace:
        if event.get("kind") == "user_message":
            users += 1
        payload = event.get("payload")
        if (
            event.get("kind") == "tool_result"
            and isinstance(payload, dict)
            and payload.get("name") == "book_slot"
            and payload.get("executed")
        ):
            return users
    return None


def _clarifications(trace: list[dict[str, Any]]) -> int:
    count = 0
    for event in trace:
        payload = event.get("payload")
        if event.get("kind") != "assistant_message" or not isinstance(payload, dict):
            continue
        if payload.get("purpose") == "clarify":
            count += 1
    return count
