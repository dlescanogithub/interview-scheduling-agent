"""Injected clocks. Scheduling logic does not call datetime.now()."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current aware instant."""

    def advance(self, seconds: float) -> None:
        """Move the clock forward. A wall clock may refuse."""


class WallClock:
    """Real wall clock. Used only to stamp a live ledger row, not to place slots."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def advance(self, seconds: float) -> None:
        raise RuntimeError("the wall clock does not move on request")


class FixedClock:
    """A clock that moves only when `advance` is called."""

    def __init__(self, current: datetime) -> None:
        if current.tzinfo is None:
            raise ValueError("clock requires an aware datetime")
        self.current = current.astimezone(UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current = self.current + timedelta(seconds=seconds)
