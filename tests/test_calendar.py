"""Calendar rules: double booking, holds, buffers, hours, and a seeded sequence."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from tests.support import CALENDAR

from scheduling_agent.calendar import CalendarError, load_calendar
from scheduling_agent.clock import FixedClock
from scheduling_agent.timeutil import overlaps, parse_iso

NOW = "2026-04-13T12:00:00+00:00"


def _calendar() -> tuple[FixedClock, object]:
    clock = FixedClock(parse_iso(NOW))
    return clock, load_calendar(CALENDAR, clock)


def test_roster_zones_and_four_interviewers() -> None:
    _clock, calendar = _calendar()
    assert set(calendar.interviewers) == {"iv-ana", "iv-bruno", "iv-camila", "iv-elena"}
    assert calendar.interviewer("iv-ana").timezone == "America/Argentina/Buenos_Aires"
    assert calendar.interviewer("iv-camila").timezone == "UTC"
    with pytest.raises(CalendarError) as exc:
        calendar.interviewer("iv-nobody")
    assert exc.value.code == "NOT_FOUND"


def test_double_book_is_rejected_by_the_calendar() -> None:
    clock, calendar = _calendar()
    start = parse_iso("2026-04-14T12:00:00Z")
    end = start + timedelta(minutes=45)
    calendar.hold(
        hold_id="h1",
        interviewer_id="iv-ana",
        candidate_id="cand-uno",
        start=start,
        end=end,
        ttl_seconds=900,
    )
    with pytest.raises(CalendarError) as exc:
        calendar.hold(
            hold_id="h2",
            interviewer_id="iv-ana",
            candidate_id="cand-dos",
            start=start,
            end=end,
            ttl_seconds=900,
        )
    assert exc.value.code == "SLOT_TAKEN"
    booking = calendar.book(booking_id="b1", hold_id="h1", candidate_id="cand-uno")
    assert booking.status == "active"
    with pytest.raises(CalendarError) as taken:
        calendar.force_book(
            booking_id="b2",
            interviewer_id="iv-ana",
            candidate_id="cand-dos",
            start=start,
            end=end,
        )
    assert taken.value.code == "SLOT_TAKEN"
    assert len(calendar.active_bookings()) == 1
    assert clock.now() == parse_iso(NOW)


def test_hold_expires_when_the_injected_clock_advances() -> None:
    clock, calendar = _calendar()
    start = parse_iso("2026-04-14T12:00:00Z")
    end = start + timedelta(minutes=45)
    calendar.hold(
        hold_id="h1",
        interviewer_id="iv-ana",
        candidate_id="cand-uno",
        start=start,
        end=end,
        ttl_seconds=60,
    )
    clock.advance(61)
    with pytest.raises(CalendarError) as exc:
        calendar.book(booking_id="b1", hold_id="h1", candidate_id="cand-uno")
    assert exc.value.code == "HOLD_EXPIRED"
    assert calendar.holds == {}


def test_buffer_blocks_the_adjacent_slot() -> None:
    _clock, calendar = _calendar()
    start = parse_iso("2026-04-14T12:00:00Z")  # 09:00 ART
    end = start + timedelta(minutes=45)
    calendar.force_book(
        booking_id="b1",
        interviewer_id="iv-ana",
        candidate_id="cand-uno",
        start=start,
        end=end,
    )
    adjacent = end  # 09:45 ART, inside the 15 minute buffer
    later = adjacent + timedelta(minutes=45)
    blocked = calendar.slot_is_free("iv-ana", adjacent, later)
    assert blocked is False
    clear = parse_iso("2026-04-14T13:00:00Z")  # 10:00 ART
    opened = calendar.slot_is_free("iv-ana", clear, clear + timedelta(minutes=45))
    assert opened is True


def test_working_hours_and_duration() -> None:
    _clock, calendar = _calendar()
    saturday = parse_iso("2026-04-18T12:00:00Z")
    slots = calendar.list_slots(
        interviewer_id="iv-ana",
        range_start=saturday,
        range_end=saturday + timedelta(hours=8),
        limit=3,
    )
    assert slots == []
    with pytest.raises(CalendarError) as exc:
        calendar.list_slots(
            interviewer_id="iv-ana",
            range_start=parse_iso("2026-04-14T12:00:00Z"),
            range_end=parse_iso("2026-04-14T20:00:00Z"),
            duration_minutes=30,
        )
    assert exc.value.code == "VALIDATION"


def test_hold_belongs_to_the_candidate_and_release() -> None:
    _clock, calendar = _calendar()
    start = parse_iso("2026-04-15T12:00:00Z")
    end = start + timedelta(minutes=45)
    calendar.hold(
        hold_id="h1",
        interviewer_id="iv-bruno",
        candidate_id="cand-uno",
        start=start,
        end=end,
        ttl_seconds=900,
    )
    with pytest.raises(CalendarError) as refused:
        calendar.book(booking_id="b1", hold_id="h1", candidate_id="cand-dos")
    assert refused.value.code == "REFUSED"
    released = calendar.release("h1")
    assert released.id == "h1"
    with pytest.raises(CalendarError) as missing:
        calendar.release("h1")
    assert missing.value.code == "NOT_FOUND"


def test_cancel_refuses_another_candidate() -> None:
    _clock, calendar = _calendar()
    start = parse_iso("2026-04-15T12:00:00Z")
    calendar.force_book(
        booking_id="b1",
        interviewer_id="iv-bruno",
        candidate_id="cand-uno",
        start=start,
        end=start + timedelta(minutes=45),
    )
    with pytest.raises(CalendarError) as exc:
        calendar.cancel("b1", "cand-dos")
    assert exc.value.code == "REFUSED"
    cancelled = calendar.cancel("b1", "cand-uno")
    assert cancelled.status == "cancelled"
    with pytest.raises(CalendarError) as again:
        calendar.cancel("b1", "cand-uno")
    assert again.value.code == "VALIDATION"
    assert calendar.bookings_for("cand-uno") == []
    assert len(calendar.bookings_for("cand-uno", active_only=False)) == 1


def test_seeded_operations_never_double_book() -> None:
    """Forty operations from random.Random(12345).

    This is a seeded sequence, not a sample of users.
    """
    rng = random.Random(12345)
    clock = FixedClock(parse_iso(NOW))
    calendar = load_calendar(CALENDAR, clock)
    pool = []
    for interviewer_id in sorted(calendar.interviewers):
        pool.extend(
            calendar.list_slots(
                interviewer_id=interviewer_id,
                range_start=parse_iso("2026-04-13T12:00:00Z"),
                range_end=parse_iso("2026-04-24T21:00:00Z"),
                limit=12,
            )
        )
    assert len(pool) >= 8
    holds: list[str] = []
    seq = 0
    for _ in range(40):
        action = rng.randrange(4)
        if action == 0:
            slot = pool[rng.randrange(len(pool))]
            candidate_id = ("cand-uno", "cand-dos", "cand-tres")[rng.randrange(3)]
            seq += 1
            try:
                hold = calendar.hold(
                    hold_id=f"h-{seq}",
                    interviewer_id=slot.interviewer_id,
                    candidate_id=candidate_id,
                    start=slot.start,
                    end=slot.end,
                    ttl_seconds=500,
                )
            except CalendarError as exc:
                assert exc.code == "SLOT_TAKEN"
            else:
                holds.append(hold.id)
        elif action == 1 and holds:
            hold_id = holds.pop(rng.randrange(len(holds)))
            hold = calendar.holds.get(hold_id)
            if hold is None:
                continue
            seq += 1
            try:
                calendar.book(
                    booking_id=f"b-{seq}",
                    hold_id=hold_id,
                    candidate_id=hold.candidate_id,
                )
            except CalendarError as exc:
                assert exc.code in {"HOLD_EXPIRED", "SLOT_TAKEN", "REFUSED"}
        elif action == 2 and holds:
            hold_id = holds.pop(rng.randrange(len(holds)))
            try:
                calendar.release(hold_id)
            except CalendarError as exc:
                assert exc.code == "NOT_FOUND"
        else:
            clock.advance(rng.randrange(0, 800))
            calendar.expire_holds()
            holds = [hold_id for hold_id in holds if hold_id in calendar.holds]
    active = calendar.active_bookings()
    for index, left in enumerate(active):
        for right in active[index + 1 :]:
            if left.interviewer_id != right.interviewer_id:
                continue
            assert overlaps(left.start, left.end, right.start, right.end) is False


def test_buenos_aires_april_morning_is_nine_in_new_york() -> None:
    """April in Buenos Aires is UTC-3; New York is on summer time (UTC-4)."""
    buenos_aires = ZoneInfo("America/Argentina/Buenos_Aires")
    new_york = ZoneInfo("America/New_York")
    summer = datetime(2026, 4, 14, 10, 0, tzinfo=buenos_aires)
    assert summer.astimezone(ZoneInfo("UTC")).hour == 13
    assert summer.astimezone(new_york).hour == 9
    assert summer.astimezone(new_york).utcoffset() == timedelta(hours=-4)
    winter = datetime(2026, 1, 13, 10, 0, tzinfo=buenos_aires)
    assert winter.astimezone(ZoneInfo("UTC")).hour == 13
    assert winter.astimezone(new_york).hour == 8
    assert winter.astimezone(new_york).utcoffset() == timedelta(hours=-5)
