"""Roster names stay aligned with the calendar fixture."""

from __future__ import annotations

from datetime import timedelta

import pytest
import yaml
from tests.support import CALENDAR

from scheduling_agent.clock import FixedClock, WallClock
from scheduling_agent.config import Settings
from scheduling_agent.roster import CANDIDATES, INTERVIEWERS
from scheduling_agent.timeutil import (
    combine_local,
    expand,
    format_local,
    overlaps,
    parse_iso,
    to_canonical,
    weekday_name,
)


def test_roster_matches_the_calendar_fixture() -> None:
    raw = yaml.safe_load(CALENDAR.read_text(encoding="utf-8"))
    for item in raw["interviewers"]:
        assert INTERVIEWERS[item["id"]]["name"] == item["name"]
        assert INTERVIEWERS[item["id"]]["email"] == item["email"]
        assert item["email"].endswith("@taller-aurora.example")
    for item in raw["candidates"]:
        assert CANDIDATES[item["id"]]["name"] == item["name"]
        assert item["email"].endswith("@mail.example")


def test_time_helpers_and_clocks() -> None:
    instant = parse_iso("2026-04-14T12:00:00Z")
    assert to_canonical(instant) == "2026-04-14T12:00:00Z"
    assert weekday_name(instant, "es", "America/Argentina/Buenos_Aires") == "martes"
    date_text, hhmm, weekday = format_local(instant, "UTC")
    assert date_text == "2026-04-14"
    assert hhmm == "12:00"
    assert weekday == "1"
    rebuilt = combine_local("2026-04-14", "09:00", "America/Argentina/Buenos_Aires")
    assert to_canonical(rebuilt) == "2026-04-14T12:00:00Z"
    start, end = expand(instant, instant + timedelta(minutes=45), 15)
    later = instant + timedelta(hours=3)
    assert overlaps(start, end, later, later + timedelta(minutes=45)) is False
    with pytest.raises(ValueError):
        parse_iso("2026-04-14T12:00:00")
    with pytest.raises(ValueError):
        to_canonical(instant.replace(tzinfo=None))
    with pytest.raises(ValueError):
        FixedClock(instant.replace(tzinfo=None))
    wall = WallClock()
    assert wall.now().tzinfo is not None
    with pytest.raises(RuntimeError):
        wall.advance(1)
    assert Settings.from_env().external_tools_enabled is True
