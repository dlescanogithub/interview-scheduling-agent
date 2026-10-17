"""Scenario gate. Exit 0 when every invariant holds, non-zero otherwise.

Retrieval hit@k is reported alongside. Labels were written with the corpus;
the number measures this retriever on that fixed set.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from scheduling_agent.invariants import CHECKS
from scheduling_agent.retrieval import BM25, bootstrap_mean, hit_at_k, load_documents
from scheduling_agent.runner import (
    ScenarioResult,
    find_root,
    load_scenarios,
    run_scenario,
)


@dataclass
class RetrievalReport:
    n: int
    hit_at_1: int
    hit_at_3: int
    hit_at_1_rate: float
    hit_at_1_low: float
    hit_at_1_high: float
    hit_at_3_rate: float
    hit_at_3_low: float
    hit_at_3_high: float
    threshold: float


@dataclass
class EvalReport:
    results: list[ScenarioResult]
    retrieval: RetrievalReport | None
    regression: bool

    @property
    def failed(self) -> list[ScenarioResult]:
        return [
            result
            for result in self.results
            if result.violations or not result.allowed_ok or result.expect_failures
        ]

    def exit_code(self) -> int:
        return 1 if self.failed else 0


def retrieval_report(root: Path, threshold: float) -> RetrievalReport:
    documents = load_documents(root / "data" / "faq")
    engine = BM25(documents)
    raw = yaml.safe_load(
        (root / "data" / "faq" / "queries.yaml").read_text(encoding="utf-8")
    )
    if not isinstance(raw, list):
        raise ValueError("queries.yaml must be a list")
    flags_1: list[bool] = []
    flags_3: list[bool] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        hits = engine.search(str(item["text"]), k=3)
        ranked = [hit.doc_id for hit in hits]
        relevant = {str(doc_id) for doc_id in item.get("relevant", [])}
        flags_1.append(hit_at_k(ranked, relevant, 1))
        flags_3.append(hit_at_k(ranked, relevant, 3))
    rate_1, low_1, high_1 = bootstrap_mean(flags_1, seed=0)
    rate_3, low_3, high_3 = bootstrap_mean(flags_3, seed=0)
    return RetrievalReport(
        n=len(flags_1),
        hit_at_1=sum(flags_1),
        hit_at_3=sum(flags_3),
        hit_at_1_rate=rate_1,
        hit_at_1_low=low_1,
        hit_at_1_high=high_1,
        hit_at_3_rate=rate_3,
        hit_at_3_low=low_3,
        hit_at_3_high=high_3,
        threshold=threshold,
    )


def run_eval(
    *,
    regression: bool = False,
    scenario_id: str | None = None,
    root: Path | None = None,
) -> EvalReport:
    base = root or find_root()
    scenarios = load_scenarios(base / "scenarios")
    if scenario_id:
        scenarios = [scenario for scenario in scenarios if scenario.id == scenario_id]
        if not scenarios:
            raise SystemExit(f"unknown scenario {scenario_id}")
    results = [
        run_scenario(scenario, root=base, regression=regression)
        for scenario in scenarios
    ]
    retrieval = None if regression else retrieval_report(base, threshold=1.0)
    return EvalReport(results=results, retrieval=retrieval, regression=regression)


def invariant_counts(results: list[ScenarioResult]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {
        name: {"pass": 0, "fail": 0} for name, _fn in CHECKS
    }
    for result in results:
        failed = {violation.name for violation in result.violations}
        for name in counts:
            if name in failed:
                counts[name]["fail"] += 1
            else:
                counts[name]["pass"] += 1
    return counts


def simulated_user_metrics(
    results: list[ScenarioResult],
) -> dict[str, float | int | None]:
    """Metrics on scripted scenarios. These are simulated users, not a panel."""
    booked = [result for result in results if result.turns_to_booking is not None]
    turns = [
        result.turns_to_booking
        for result in booked
        if result.turns_to_booking is not None
    ]
    clarifications = [result.clarifications for result in booked]
    handoffs = sum(1 for result in results if result.handoff)
    clarify_messages = sum(result.clarifications for result in results)
    return {
        "scenarios": len(results),
        "booked_scenarios": len(booked),
        "mean_turns_to_booking": (sum(turns) / len(turns)) if turns else None,
        "mean_clarifications_per_booking": (
            (sum(clarifications) / len(clarifications)) if clarifications else None
        ),
        "clarify_messages": clarify_messages,
        "handoff_rate": (handoffs / len(results)) if results else None,
        "handoffs": handoffs,
    }


def render_report(report: EvalReport) -> str:
    lines: list[str] = []
    mode = "regression" if report.regression else "gate"
    lines.append(f"eval {mode}: {'FAIL' if report.failed else 'PASS'}")
    passed = len(report.results) - len(report.failed)
    total = len(report.results)
    lines.append(f"scenarios: {passed}/{total} passed")
    counts = invariant_counts(report.results)
    lines.append(f"{'invariant':<42} {'pass':>6} {'fail':>6}")
    for name, row in counts.items():
        lines.append(f"{name:<42} {row['pass']:>6} {row['fail']:>6}")
    violation_total = sum(len(result.violations) for result in report.results)
    lines.append(f"violations: {violation_total}")
    if not report.regression:
        metrics = simulated_user_metrics(report.results)

        def _fmt(value: object) -> str:
            return f"{value:.2f}" if isinstance(value, float) else str(value)

        clarifications = _fmt(metrics["mean_clarifications_per_booking"])
        lines.append(
            "simulated users: "
            f"mean_turns_to_booking={_fmt(metrics['mean_turns_to_booking'])} "
            f"mean_clarifications_per_booking={clarifications} "
            f"clarify_messages={metrics['clarify_messages']} "
            f"handoff_rate={_fmt(metrics['handoff_rate'])} "
            f"handoffs={metrics['handoffs']} "
            f"n={metrics['scenarios']}"
        )
        if report.retrieval is not None:
            retrieval = report.retrieval
            hit1_ci = f"{retrieval.hit_at_1_low:.3f},{retrieval.hit_at_1_high:.3f}"
            hit3_ci = f"{retrieval.hit_at_3_low:.3f},{retrieval.hit_at_3_high:.3f}"
            lines.append(
                "retrieval: "
                f"hit@1={retrieval.hit_at_1}/{retrieval.n} "
                f"rate={retrieval.hit_at_1_rate:.3f} "
                f"bootstrap95=[{hit1_ci}] "
                f"hit@3={retrieval.hit_at_3}/{retrieval.n} "
                f"rate={retrieval.hit_at_3_rate:.3f} "
                f"bootstrap95=[{hit3_ci}] "
                "labels=authored_with_corpus "
                "ci=resampled_queries_not_a_model_comparison"
            )
    for result in report.failed:
        names = ", ".join(violation.name for violation in result.violations) or "none"
        lines.append(
            f"FAIL {result.scenario_id} terminal={result.terminal} "
            f"invariants={names} allowed_ok={result.allowed_ok} "
            f"expect={result.expect_failures}"
        )
        for violation in result.violations:
            lines.append(f"  - {violation.name}: {violation.detail}")
    return "\n".join(lines) + "\n"
