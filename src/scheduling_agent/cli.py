"""Command line. `python -m scheduling_agent <subcommand>`."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace

from scheduling_agent import __version__
from scheduling_agent.config import (
    LiveConfigError,
    Settings,
    assert_live_ready,
    load_dotenv_file,
)
from scheduling_agent.evalgate import render_report, run_eval
from scheduling_agent.live import LiveProvider, SpendLedger, UrllibTransport
from scheduling_agent.logging_setup import redact
from scheduling_agent.runner import (
    ScenarioResult,
    find_root,
    load_scenarios,
    run_scenario,
)
from scheduling_agent.secretscan import main as secretscan_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scheduling_agent")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="print a scripted happy-path transcript")
    demo.add_argument("--interactive", action="store_true")
    demo.add_argument("--scenario", default="happy_path")

    evaluate = sub.add_parser("eval", help="run the invariant gate")
    evaluate.add_argument("--regression", action="store_true")
    evaluate.add_argument("--scenario", default=None)

    live = sub.add_parser("live", help="optional real-model run, off unless LIVE_LLM=1")
    live.add_argument("--scenario", default="happy_path")
    live.add_argument("--max-turns", type=int, default=12)

    sub.add_parser("secretscan", help="scan the working tree for credential shapes")

    args = parser.parse_args(argv)
    if args.command == "demo":
        return cmd_demo(args.scenario, interactive=args.interactive)
    if args.command == "eval":
        return cmd_eval(regression=args.regression, scenario_id=args.scenario)
    if args.command == "live":
        return cmd_live(args.scenario, args.max_turns)
    if args.command == "secretscan":
        return secretscan_main()
    parser.print_help()
    return 2


def cmd_eval(*, regression: bool, scenario_id: str | None) -> int:
    report = run_eval(regression=regression, scenario_id=scenario_id)
    sys.stdout.write(render_report(report))
    return report.exit_code()


def cmd_demo(scenario_id: str, *, interactive: bool) -> int:
    if interactive:
        return _interactive()
    root = find_root()
    matches = [
        scenario
        for scenario in load_scenarios(root / "scenarios")
        if scenario.id == scenario_id
    ]
    if not matches:
        print(f"unknown scenario {scenario_id}", file=sys.stderr)
        return 2
    result = run_scenario(matches[0], root=root)
    sys.stdout.write(_transcript(result.messages, result.trace))
    print(f"terminal={result.terminal} outbox={result.outbox} booked={result.booked}")
    return 0 if not result.violations else 1


def cmd_live(scenario_id: str, max_turns: int) -> int:
    load_dotenv_file()
    settings = replace(Settings.from_env(), max_turns=max_turns)
    try:
        assert_live_ready(settings)
    except LiveConfigError as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 2
    root = find_root()
    matches = [
        scenario
        for scenario in load_scenarios(root / "scenarios")
        if scenario.id == scenario_id
    ]
    if not matches:
        print(f"unknown scenario {scenario_id}", file=sys.stderr)
        return 2
    ledger = SpendLedger(root / "var" / "live-evals" / "ledger.jsonl")
    provider = LiveProvider(settings, UrllibTransport(), ledger)
    result = run_scenario(matches[0], root=root, settings=settings, provider=provider)
    sys.stdout.write(_transcript(result.messages, result.trace))
    for violation in result.violations:
        print(f"- {violation.name}: {violation.detail}")
    last_status = ledger.rows[-1]["cost_status"] if ledger.rows else "none"
    print(f"ledger_rows={len(ledger.rows)} cost_status_last={last_status}")
    print(render_live_result(result), end="")
    return live_outcome(result)[1]


def live_outcome(result: ScenarioResult) -> tuple[str, int]:
    """Separate a clean invariant trace from a finished booking.

    PASS is only both. A trace with no violations and no booking is INCOMPLETE,
    not PASS. FAIL means an invariant broke or a tool outside the allow-list ran.
    """
    invariants_passed = not result.violations and result.allowed_ok
    task_completed = not result.expect_failures
    if not invariants_passed:
        return "FAIL", 1
    if not task_completed:
        return "INCOMPLETE", 3
    return "PASS", 0


def render_live_result(result: ScenarioResult) -> str:
    """Text the live command prints. The word PASS appears only for a real PASS."""
    label, _code = live_outcome(result)
    invariants_passed = not result.violations and result.allowed_ok
    task_completed = not result.expect_failures
    if result.expect_failures:
        listed = "\n".join(f"- {item}" for item in result.expect_failures)
        unmet = f"expect_failures:\n{listed}\n"
    else:
        unmet = "expect_failures: none\n"
    return (
        f"{unmet}"
        f"invariants_passed={str(invariants_passed).lower()}\n"
        f"task_completed={str(task_completed).lower()}\n"
        f"live result: {label}\n"
    )


def _interactive() -> int:
    """Terminal loop. Recruiter decisions are `/approve` and `/reject`."""
    root = find_root()
    from scheduling_agent.agent import Agent
    from scheduling_agent.approvals import ApprovalStore
    from scheduling_agent.calendar import load_calendar
    from scheduling_agent.clock import FixedClock
    from scheduling_agent.config import Settings
    from scheduling_agent.policy import ScriptedProvider
    from scheduling_agent.retrieval import BM25, load_documents
    from scheduling_agent.roster import CANDIDATES, other_markers
    from scheduling_agent.runtime import RunContext
    from scheduling_agent.timeutil import parse_iso
    from scheduling_agent.trace import Trace

    settings = Settings()
    clock = FixedClock(parse_iso(settings.now_iso))
    calendar = load_calendar(root / "data" / "calendar" / "taller_aurora.yaml", clock)
    documents = load_documents(root / "data" / "faq")
    candidate = calendar.candidates["cand-one"]
    ctx = RunContext(
        run_id="run-interactive",
        candidate_id=candidate.id,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        candidate_tz=candidate.timezone,
        lang="en",
        clock=clock,
        calendar=calendar,
        approvals=ApprovalStore(clock, settings.approval_ttl_seconds),
        trace=Trace("run-interactive", clock),
        retriever=BM25(documents),
        settings=settings,
        protected_ids=[key for key in CANDIDATES if key != candidate.id],
        protected_names=list(other_markers(candidate.id)),
        known_doc_ids=[document.id for document in documents],
        external_enabled=settings.external_tools_enabled,
    )
    agent = Agent(ctx, ScriptedProvider())
    print("Taller Aurora (scripted). /approve, /reject, quit.")
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        text = line.strip()
        if text in {"quit", "exit"}:
            break
        if text == "/approve":
            print(agent.handle_recruiter("approve"))
        elif text == "/reject":
            print(agent.handle_recruiter("reject"))
        elif text:
            print(agent.handle_user(text))
    agent.finalize()
    return 0


def _transcript(
    messages: list[dict[str, object]], trace: list[dict[str, object]]
) -> str:
    lines: list[str] = ["# scripted transcript", ""]
    for message in messages:
        role = str(message.get("role"))
        if role == "system" and "recruiter_decision=" not in str(
            message.get("content") or ""
        ):
            continue
        if role == "system":
            lines.append(f"[recruiter] {message.get('content')}")
            continue
        if role == "tool":
            lines.append(f"[tool] {message.get('content')}")
            continue
        calls = message.get("tool_calls")
        if calls:
            lines.append(f"[assistant calls] {calls}")
        content = str(message.get("content") or "").strip()
        if content:
            lines.append(f"[{role}] {content}")
        lines.append("")
    lines.append(
        "# trace kinds: " + ",".join(str(event.get("kind")) for event in trace)
    )
    lines.append("")
    return "\n".join(lines)


def run_interactive_lines(lines: list[str]) -> list[str]:
    """Non-interactive helper used by tests. Returns assistant replies."""
    replies: list[str] = []
    root = find_root()
    from scheduling_agent.agent import Agent
    from scheduling_agent.approvals import ApprovalStore
    from scheduling_agent.calendar import load_calendar
    from scheduling_agent.clock import FixedClock
    from scheduling_agent.config import Settings
    from scheduling_agent.policy import ScriptedProvider
    from scheduling_agent.retrieval import BM25, load_documents
    from scheduling_agent.roster import CANDIDATES, other_markers
    from scheduling_agent.runtime import RunContext
    from scheduling_agent.timeutil import parse_iso
    from scheduling_agent.trace import Trace

    settings = Settings()
    clock = FixedClock(parse_iso(settings.now_iso))
    calendar = load_calendar(root / "data" / "calendar" / "taller_aurora.yaml", clock)
    documents = load_documents(root / "data" / "faq")
    candidate = calendar.candidates["cand-one"]
    ctx = RunContext(
        run_id="run-lines",
        candidate_id=candidate.id,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        candidate_tz=candidate.timezone,
        lang="en",
        clock=clock,
        calendar=calendar,
        approvals=ApprovalStore(clock, settings.approval_ttl_seconds),
        trace=Trace("run-lines", clock),
        retriever=BM25(documents),
        settings=settings,
        protected_ids=[key for key in CANDIDATES if key != candidate.id],
        protected_names=list(other_markers(candidate.id)),
        known_doc_ids=[document.id for document in documents],
        external_enabled=True,
    )
    agent = Agent(ctx, ScriptedProvider())
    for line in lines:
        if line == "/approve":
            replies.append(agent.handle_recruiter("approve"))
        elif line == "/reject":
            replies.append(agent.handle_recruiter("reject"))
        else:
            replies.append(agent.handle_user(line))
    agent.finalize()
    return replies
