"""CLI, eval gate, cost cap, and the forced regression."""

from __future__ import annotations

from dataclasses import replace

import pytest
from tests.support import make_ctx

from scheduling_agent.agent import Agent, SpendCapError
from scheduling_agent.cassette import CompletionRequest, CompletionResponse
from scheduling_agent.cli import main, run_interactive_lines
from scheduling_agent.config import Settings, load_dotenv_file
from scheduling_agent.evalgate import run_eval
from scheduling_agent.policy import ScriptedProvider
from scheduling_agent.providers import FailNProvider


def test_gate_passes_and_regression_exits_1() -> None:
    report = run_eval()
    assert report.exit_code() == 0
    assert len(report.results) == 26
    assert report.failed == []
    assert report.retrieval is not None
    assert report.retrieval.n == 30
    assert report.retrieval.hit_at_1 == 30

    broken = run_eval(regression=True)
    assert broken.exit_code() == 1
    names = {item.name for result in broken.results for item in result.violations}
    assert "book_preceded_by_user_confirmation" in names
    assert "no_external_without_matching_approval" in names
    assert "no_send_claim_without_outbox" in names
    happy = next(
        result for result in broken.results if result.scenario_id == "happy_path"
    )
    assert happy.expect_failures == []


def test_cli_demo_eval_and_live_refusal(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo", "--scenario", "happy_path"]) == 0
    assert "terminal=" in capsys.readouterr().out
    assert main(["demo", "--scenario", "missing-scenario"]) == 2
    assert main(["eval", "--scenario", "happy_path"]) == 0
    assert main(["eval", "--regression", "--scenario", "happy_path"]) == 1
    assert main(["live", "--scenario", "happy_path"]) == 2
    with pytest.raises(SystemExit):
        main([])


def test_interactive_lines_and_quit(monkeypatch: pytest.MonkeyPatch) -> None:
    replies = run_interactive_lines(
        ["Quiero una entrevista con Ana Luz el 14 de abril de 2026."]
    )
    assert replies
    answers = iter(["hola", "salir"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    assert main(["demo", "--interactive"]) == 0


def test_cost_cap_handoff_does_not_call_the_provider() -> None:
    class Boom:
        def complete(self, request: CompletionRequest) -> CompletionResponse:
            raise AssertionError(request)

    settings = Settings(
        sim_price_in_per_mtok=1000.0,
        sim_price_out_per_mtok=1000.0,
        max_cost_usd=0.01,
        max_output_tokens_reservation=200,
    )
    ctx = make_ctx(settings)
    agent = Agent(ctx, Boom())
    text = agent.handle_user("hola")
    assert ctx.terminal == "handoff"
    assert "persona" in text
    assert ctx.tool_calls == 0


def test_spend_cap_error_is_not_retried() -> None:
    sleeps: list[float] = []

    class Once:
        def complete(self, request: CompletionRequest) -> CompletionResponse:
            raise SpendCapError("stop")

    ctx = make_ctx()
    agent = Agent(ctx, Once(), sleeper=sleeps.append)
    agent.handle_user("hola")
    assert sleeps == []
    assert ctx.terminal == "handoff"


def test_provider_errors_retry_then_handoff() -> None:
    ctx = make_ctx(replace(Settings(), retry_attempts=2))
    agent = Agent(ctx, FailNProvider(ScriptedProvider(), 5))
    agent.handle_user("hola")
    assert ctx.terminal == "handoff"
    assert any(event.kind == "provider_error" for event in ctx.trace.events)


def test_max_turns_hands_off_before_a_call() -> None:
    class Boom:
        def complete(self, request: CompletionRequest) -> CompletionResponse:
            raise AssertionError(request)

    ctx = make_ctx(Settings(max_turns=0))
    agent = Agent(ctx, Boom())
    agent.handle_user("hola")
    assert ctx.terminal == "handoff"


def test_dotenv_loader(monkeypatch: pytest.MonkeyPatch, tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# comment\n\nMAX_TURNS="4"\nEMPTY=\nNOEQUALS\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("MAX_TURNS", "9")
    load_dotenv_file(env_file)
    assert __import__("os").environ["MAX_TURNS"] == "9"
    monkeypatch.delenv("MAX_TURNS")
    load_dotenv_file(env_file)
    assert __import__("os").environ["MAX_TURNS"] == "4"
    load_dotenv_file(tmp_path / "missing.env")
    monkeypatch.setenv("LIVE_LLM", "yes")
    monkeypatch.setenv("MAX_LIVE_SPEND_USD", "")
    monkeypatch.setenv("MAX_LIVE_TOKENS", "")
    settings = Settings.from_env()
    assert settings.live_llm is True
    assert settings.max_live_spend_usd is None
    assert settings.max_turns == 4
    assert settings.scheduler_model() == ""
