"""Shared fixtures for the synthetic Taller Aurora lab."""

from __future__ import annotations

from pathlib import Path

from scheduling_agent.approvals import ApprovalStore
from scheduling_agent.calendar import load_calendar
from scheduling_agent.clock import FixedClock
from scheduling_agent.config import Settings
from scheduling_agent.retrieval import BM25, load_documents
from scheduling_agent.roster import CANDIDATES, other_markers
from scheduling_agent.runtime import RunContext
from scheduling_agent.timeutil import parse_iso
from scheduling_agent.trace import Trace

ROOT = Path(__file__).resolve().parents[1]
CALENDAR = ROOT / "data" / "calendar" / "taller_aurora.yaml"
FAQ = ROOT / "data" / "faq"


def make_ctx(
    settings: Settings | None = None,
    candidate_id: str = "cand-one",
) -> RunContext:
    active = settings if settings is not None else Settings()
    clock = FixedClock(parse_iso(active.now_iso))
    calendar = load_calendar(CALENDAR, clock)
    documents = load_documents(FAQ)
    candidate = calendar.candidates[candidate_id]
    return RunContext(
        run_id="run-test",
        candidate_id=candidate.id,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        candidate_tz=candidate.timezone,
        lang="en",
        clock=clock,
        calendar=calendar,
        approvals=ApprovalStore(clock, active.approval_ttl_seconds),
        trace=Trace("run-test", clock),
        retriever=BM25(documents),
        settings=active,
        protected_ids=[key for key in CANDIDATES if key != candidate.id],
        protected_names=list(other_markers(candidate.id)),
        known_doc_ids=[document.id for document in documents],
        bypass_gates=active.bypass_gates,
        external_enabled=active.external_tools_enabled,
    )
