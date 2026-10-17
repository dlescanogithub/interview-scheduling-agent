"""Bounded retries. Attempts, backoff cap and jitter are all injected."""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class RetryExhausted(Exception):
    """The last attempt failed and the attempt budget is spent."""

    def __init__(self, attempts: int, last: BaseException) -> None:
        super().__init__(f"gave up after {attempts} attempts: {last}")
        self.attempts = attempts
        self.last = last


def retry_call(
    fn: Callable[[], T],
    *,
    attempts: int,
    base_seconds: float,
    cap_seconds: float,
    sleeper: Callable[[float], None],
    rng: random.Random,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Call `fn` up to `attempts` times. Sleep is capped and includes jitter.

    The sleeper and RNG are injected so tests do not wait on a wall clock.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    last_error: BaseException | None = None
    for index in range(attempts):
        try:
            return fn()
        except retry_on as exc:
            last_error = exc
            if index == attempts - 1:
                break
            growth = base_seconds * (2**index)
            delay = min(cap_seconds, growth)
            jitter = rng.random() * delay * 0.2
            sleeper(min(cap_seconds, delay + jitter))
    assert last_error is not None
    raise RetryExhausted(attempts, last_error)
