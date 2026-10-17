"""In-memory calendar for the fictional co-op Taller Aurora.

Double-booking is rejected here, not only by the agent. Time zones use
`zoneinfo`. The clock is injected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from scheduling_agent.clock import Clock
from scheduling_agent.timeutil import (
    expand,
    overlaps,
    parse_hhmm,
    parse_iso,
    to_canonical,
)

SLOT_STEP_MINUTES = 60


class CalendarError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass
class Interviewer:
    id: str
    name: str
    email: str
    timezone: str
    slot_minutes: int
    buffer_minutes: int
    working_hours: dict[int, tuple[time, time]]
    busy: list[tuple[datetime, datetime]] = field(default_factory=list)


@dataclass
class Candidate:
    id: str
    name: str
    email: str
    timezone: str


@dataclass
class Hold:
    id: str
    interviewer_id: str
    candidate_id: str
    start: datetime
    end: datetime
    expires_at: datetime


@dataclass
class Booking:
    id: str
    interviewer_id: str
    candidate_id: str
    start: datetime
    end: datetime
    status: str = "active"


@dataclass(frozen=True)
class Slot:
    interviewer_id: str
    start: datetime
    end: datetime
    duration_minutes: int

    def canonical_start(self) -> str:
        return to_canonical(self.start)

    def canonical_end(self) -> str:
        return to_canonical(self.end)


def within_working_hours(
    interviewer: Interviewer, start: datetime, end: datetime
) -> bool:
    zone = ZoneInfo(interviewer.timezone)
    local_start = start.astimezone(zone)
    local_end = end.astimezone(zone)
    if local_start.date() != local_end.date():
        return False
    window = interviewer.working_hours.get(local_start.weekday())
    if window is None:
        return False
    open_t, close_t = window
    return local_start.time() >= open_t and local_end.time() <= close_t


class Calendar:
    """Holds, bookings and busy blocks for one synthetic hiring team."""

    def __init__(
        self,
        interviewers: dict[str, Interviewer],
        candidates: dict[str, Candidate],
        clock: Clock,
    ) -> None:
        self.interviewers = interviewers
        self.candidates = candidates
        self.clock = clock
        self.holds: dict[str, Hold] = {}
        self.bookings: dict[str, Booking] = {}

    def interviewer(self, interviewer_id: str) -> Interviewer:
        try:
            return self.interviewers[interviewer_id]
        except KeyError as exc:
            raise CalendarError(
                "NOT_FOUND", f"unknown interviewer {interviewer_id}"
            ) from exc

    def expire_holds(self) -> None:
        now = self.clock.now()
        self.holds = {
            hold_id: hold
            for hold_id, hold in self.holds.items()
            if hold.expires_at > now
        }

    def _blocked(
        self, interviewer_id: str, *, ignore_hold: str | None = None
    ) -> list[tuple[datetime, datetime]]:
        self.expire_holds()
        interviewer = self.interviewer(interviewer_id)
        blocks: list[tuple[datetime, datetime]] = []
        for start, end in interviewer.busy:
            blocks.append(expand(start, end, interviewer.buffer_minutes))
        for booking in self.bookings.values():
            if booking.interviewer_id == interviewer_id and booking.status == "active":
                blocks.append(
                    expand(booking.start, booking.end, interviewer.buffer_minutes)
                )
        for hold in self.holds.values():
            if hold.interviewer_id == interviewer_id and hold.id != ignore_hold:
                blocks.append(expand(hold.start, hold.end, interviewer.buffer_minutes))
        return blocks

    def slot_is_free(
        self,
        interviewer_id: str,
        start: datetime,
        end: datetime,
        *,
        ignore_hold: str | None = None,
    ) -> bool:
        interviewer = self.interviewer(interviewer_id)
        if not within_working_hours(interviewer, start, end):
            return False
        for block_start, block_end in self._blocked(
            interviewer_id, ignore_hold=ignore_hold
        ):
            if overlaps(start, end, block_start, block_end):
                return False
        return True

    def list_slots(
        self,
        *,
        interviewer_id: str,
        range_start: datetime,
        range_end: datetime,
        duration_minutes: int | None = None,
        limit: int = 3,
    ) -> list[Slot]:
        interviewer = self.interviewer(interviewer_id)
        duration = duration_minutes or interviewer.slot_minutes
        if duration != interviewer.slot_minutes:
            raise CalendarError(
                "VALIDATION",
                f"duration must be {interviewer.slot_minutes} minutes",
            )
        zone = ZoneInfo(interviewer.timezone)
        slots: list[Slot] = []
        day = range_start.astimezone(zone).date()
        last = range_end.astimezone(zone).date()
        while day <= last and len(slots) < limit:
            window = interviewer.working_hours.get(day.weekday())
            if window is not None:
                open_t, close_t = window
                cursor = datetime(
                    day.year,
                    day.month,
                    day.day,
                    open_t.hour,
                    open_t.minute,
                    tzinfo=zone,
                )
                close = datetime(
                    day.year,
                    day.month,
                    day.day,
                    close_t.hour,
                    close_t.minute,
                    tzinfo=zone,
                )
                while (
                    cursor + timedelta(minutes=duration) <= close and len(slots) < limit
                ):
                    start = cursor.astimezone(UTC)
                    end = start + timedelta(minutes=duration)
                    if start >= range_start.astimezone(
                        UTC
                    ) and end <= range_end.astimezone(UTC):
                        if self.slot_is_free(interviewer_id, start, end):
                            slots.append(
                                Slot(
                                    interviewer_id=interviewer_id,
                                    start=start,
                                    end=end,
                                    duration_minutes=duration,
                                )
                            )
                    cursor += timedelta(minutes=SLOT_STEP_MINUTES)
            day += timedelta(days=1)
        return slots

    def hold(
        self,
        *,
        hold_id: str,
        interviewer_id: str,
        candidate_id: str,
        start: datetime,
        end: datetime,
        ttl_seconds: int,
    ) -> Hold:
        if candidate_id not in self.candidates:
            raise CalendarError("NOT_FOUND", f"unknown candidate {candidate_id}")
        if not self.slot_is_free(interviewer_id, start, end):
            raise CalendarError("SLOT_TAKEN", "slot is not free")
        hold = Hold(
            id=hold_id,
            interviewer_id=interviewer_id,
            candidate_id=candidate_id,
            start=start,
            end=end,
            expires_at=self.clock.now() + timedelta(seconds=ttl_seconds),
        )
        self.holds[hold_id] = hold
        return hold

    def release(self, hold_id: str) -> Hold:
        self.expire_holds()
        try:
            return self.holds.pop(hold_id)
        except KeyError as exc:
            raise CalendarError("NOT_FOUND", f"unknown hold {hold_id}") from exc

    def book(
        self,
        *,
        booking_id: str,
        hold_id: str,
        candidate_id: str,
    ) -> Booking:
        self.expire_holds()
        hold = self.holds.get(hold_id)
        if hold is None:
            raise CalendarError("HOLD_EXPIRED", "hold is missing or expired")
        if hold.candidate_id != candidate_id:
            raise CalendarError("REFUSED", "hold belongs to another candidate")
        if not self.slot_is_free(
            hold.interviewer_id, hold.start, hold.end, ignore_hold=hold.id
        ):
            raise CalendarError("SLOT_TAKEN", "slot was taken")
        booking = Booking(
            id=booking_id,
            interviewer_id=hold.interviewer_id,
            candidate_id=candidate_id,
            start=hold.start,
            end=hold.end,
            status="active",
        )
        self.bookings[booking_id] = booking
        self.holds.pop(hold_id, None)
        return booking

    def force_book(
        self,
        *,
        booking_id: str,
        interviewer_id: str,
        candidate_id: str,
        start: datetime,
        end: datetime,
    ) -> Booking:
        """Test/fixture helper. Still rejects overlaps and hours violations."""
        if not self.slot_is_free(interviewer_id, start, end):
            raise CalendarError("SLOT_TAKEN", "slot is not free")
        booking = Booking(
            id=booking_id,
            interviewer_id=interviewer_id,
            candidate_id=candidate_id,
            start=start,
            end=end,
        )
        self.bookings[booking_id] = booking
        return booking

    def cancel(self, booking_id: str, candidate_id: str) -> Booking:
        booking = self.bookings.get(booking_id)
        if booking is None:
            raise CalendarError("NOT_FOUND", f"unknown booking {booking_id}")
        if booking.candidate_id != candidate_id:
            raise CalendarError("REFUSED", "booking belongs to another candidate")
        if booking.status != "active":
            raise CalendarError("VALIDATION", "booking is not active")
        booking.status = "cancelled"
        return booking

    def bookings_for(
        self, candidate_id: str, *, active_only: bool = True
    ) -> list[Booking]:
        rows = [
            row for row in self.bookings.values() if row.candidate_id == candidate_id
        ]
        if active_only:
            rows = [row for row in rows if row.status == "active"]
        return sorted(rows, key=lambda row: row.start)

    def active_bookings(self) -> list[Booking]:
        return [row for row in self.bookings.values() if row.status == "active"]

    def snapshot(self) -> dict[str, Any]:
        """Rules and bookings, so invariants can judge the final calendar."""
        interviewers: dict[str, Any] = {}
        for interviewer in self.interviewers.values():
            interviewers[interviewer.id] = {
                "timezone": interviewer.timezone,
                "slot_minutes": interviewer.slot_minutes,
                "buffer_minutes": interviewer.buffer_minutes,
                "working_hours": {
                    str(day): [start.strftime("%H:%M"), end.strftime("%H:%M")]
                    for day, (start, end) in sorted(interviewer.working_hours.items())
                },
                "busy": [
                    {"start": to_canonical(start), "end": to_canonical(end)}
                    for start, end in interviewer.busy
                ],
            }
        bookings = [
            {
                "id": booking.id,
                "interviewer_id": booking.interviewer_id,
                "candidate_id": booking.candidate_id,
                "start": to_canonical(booking.start),
                "end": to_canonical(booking.end),
                "status": booking.status,
            }
            for booking in sorted(self.bookings.values(), key=lambda row: row.id)
        ]
        return {"interviewers": interviewers, "bookings": bookings}


def _hours(raw: dict[str, list[str]]) -> dict[int, tuple[time, time]]:
    parsed: dict[int, tuple[time, time]] = {}
    for key, window in raw.items():
        parsed[int(key)] = (parse_hhmm(window[0]), parse_hhmm(window[1]))
    return parsed


def load_calendar(path: Path, clock: Clock) -> Calendar:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("calendar fixture must be a mapping")
    interviewers: dict[str, Interviewer] = {}
    for item in raw["interviewers"]:
        busy = [
            (parse_iso(block["start"]), parse_iso(block["end"]))
            for block in item.get("busy", [])
        ]
        interviewers[item["id"]] = Interviewer(
            id=item["id"],
            name=item["name"],
            email=item["email"],
            timezone=item["timezone"],
            slot_minutes=int(item["slot_minutes"]),
            buffer_minutes=int(item["buffer_minutes"]),
            working_hours=_hours(item["working_hours"]),
            busy=busy,
        )
    candidates: dict[str, Candidate] = {}
    for item in raw["candidates"]:
        candidates[item["id"]] = Candidate(
            id=item["id"],
            name=item["name"],
            email=item["email"],
            timezone=item["timezone"],
        )
    return Calendar(interviewers, candidates, clock)
