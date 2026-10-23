"""Cassette replay never opens a socket. Retries use an injected sleeper."""

from __future__ import annotations

import random

import pytest

from scheduling_agent.cassette import (
    CassetteMiss,
    CassetteProvider,
    CompletionRequest,
    CompletionResponse,
    request_key,
)
from scheduling_agent.retry import RetryExhausted, retry_call


def test_missing_cassette_key_raises_and_does_not_touch_sockets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("socket opened")

    monkeypatch.setattr("socket.socket", boom)
    provider = CassetteProvider({})
    request = CompletionRequest(
        messages=[{"role": "user", "content": "hello"}], tools=[]
    )
    with pytest.raises(CassetteMiss):
        provider.complete(request)


def test_request_key_ignores_dict_order() -> None:
    left = CompletionRequest(
        messages=[{"b": 1, "a": 2}],
        tools=[{"name": "list_availability"}],
        model="lab",
    )
    right = CompletionRequest(
        messages=[{"a": 2, "b": 1}],
        tools=[{"name": "list_availability"}],
        model="lab",
    )
    assert request_key(left) == request_key(right)
    stored = CompletionResponse(text="ok")
    provider = CassetteProvider({request_key(left): stored})
    assert provider.complete(right).text == "ok"


def test_retry_sleeps_with_cap_and_jitter() -> None:
    sleeps: list[float] = []
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise TimeoutError("not yet")
        return "ok"

    result = retry_call(
        flaky,
        attempts=3,
        base_seconds=10.0,
        cap_seconds=1.0,
        sleeper=sleeps.append,
        rng=random.Random(0),
    )
    assert result == "ok"
    assert calls["n"] == 3
    assert len(sleeps) == 2
    assert all(0 < delay <= 1.0 for delay in sleeps)


def test_retry_gives_up_and_rejects_zero_attempts() -> None:
    with pytest.raises(ValueError):
        retry_call(
            lambda: "no",
            attempts=0,
            base_seconds=0.1,
            cap_seconds=0.1,
            sleeper=lambda _seconds: None,
            rng=random.Random(0),
        )

    def always() -> str:
        raise RuntimeError("down")

    with pytest.raises(RetryExhausted) as exc:
        retry_call(
            always,
            attempts=2,
            base_seconds=0.1,
            cap_seconds=0.2,
            sleeper=lambda _seconds: None,
            rng=random.Random(1),
        )
    assert exc.value.attempts == 2
    with pytest.raises(RuntimeError):
        retry_call(
            always,
            attempts=2,
            base_seconds=0.1,
            cap_seconds=0.2,
            sleeper=lambda _seconds: None,
            rng=random.Random(1),
            retry_on=(TimeoutError,),
        )
