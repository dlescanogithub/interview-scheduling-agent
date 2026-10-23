"""Live mode refuses to start or to spend without a fake transport. No sockets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scheduling_agent.agent import ProviderError, SpendCapError
from scheduling_agent.cassette import CompletionRequest
from scheduling_agent.clock import FixedClock
from scheduling_agent.config import LiveConfigError, Settings, assert_live_ready
from scheduling_agent.live import (
    LiveProvider,
    SpendLedger,
    UrllibTransport,
    chat_url,
    estimate_tokens,
    input_cost_usd,
)
from scheduling_agent.timeutil import parse_iso

KEY = "sk" + "-" + "a1B2c3D4e5F6g7H8i9J0"


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "live_llm": True,
        "llm_base_url": "https://llm.example/v1",
        "llm_api_key": KEY,
        "llm_model": "lab-model",
        "max_live_spend_usd": 1.0,
        "llm_price_in_per_mtok": 1.0,
        "llm_price_out_per_mtok": 1.0,
        "llm_max_output_tokens": 32,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _request(text: str = "hello") -> CompletionRequest:
    return CompletionRequest(messages=[{"role": "user", "content": text}], tools=[])


class FakeTransport:
    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.payload = payload or {
            "choices": [{"message": {"content": "listo", "tool_calls": []}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2},
        }
        self.error = error
        self.calls = 0
        self.seen_headers: dict[str, str] = {}

    def post(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        self.calls += 1
        self.seen_headers = headers
        if self.error is not None:
            raise self.error
        assert url.endswith("/chat/completions")
        assert timeout == 60
        return self.payload


def test_assert_live_ready_refuses_incomplete_config() -> None:
    with pytest.raises(LiveConfigError):
        assert_live_ready(Settings())
    with pytest.raises(LiveConfigError):
        assert_live_ready(_settings(max_live_spend_usd=0))
    with pytest.raises(LiveConfigError):
        assert_live_ready(_settings(llm_api_key=""))
    with pytest.raises(LiveConfigError):
        assert_live_ready(
            _settings(
                llm_price_in_per_mtok=None,
                llm_price_out_per_mtok=None,
                max_live_tokens=None,
            )
        )
    assert_live_ready(
        _settings(
            llm_price_in_per_mtok=None,
            llm_price_out_per_mtok=None,
            max_live_tokens=1000,
        )
    )


def test_reservation_refuses_before_the_transport_is_called(tmp_path: Path) -> None:
    transport = FakeTransport()
    ledger = SpendLedger(tmp_path / "ledger.jsonl")
    provider = LiveProvider(
        _settings(max_live_spend_usd=0.0000001, llm_price_in_per_mtok=1000.0),
        transport,
        ledger,
        clock=FixedClock(parse_iso("2026-04-13T12:00:00Z")),
    )
    with pytest.raises(SpendCapError):
        provider.complete(_request())
    assert transport.calls == 0
    assert ledger.rows == []


def test_ledger_row_omits_the_key(tmp_path: Path) -> None:
    transport = FakeTransport(
        {
            "choices": [
                {
                    "message": {
                        "content": "ok",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "function": {
                                    "name": "search_faq",
                                    "arguments": '{"query": "privacidad"}',
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        }
    )
    ledger = SpendLedger(tmp_path / "ledger.jsonl")
    clock = FixedClock(parse_iso("2026-04-13T12:00:00Z"))
    provider = LiveProvider(
        _settings(llm_model_scheduler="scheduler-lab"),
        transport,
        ledger,
        clock=clock,
    )
    response = provider.complete(_request())
    assert response.tool_calls[0].name == "search_faq"
    assert ledger.rows[0]["cost_status"] == "computed"
    assert ledger.rows[0]["model"] == "scheduler-lab"
    blob = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")
    assert KEY not in blob
    assert KEY not in json.dumps(ledger.rows)


def test_cached_price_discounts_reported_usage(tmp_path: Path) -> None:
    """VERIFY_REPORT_11 arithmetic: full input price vs a cached price.

    35629 in, 24576 cached, 716 out. Full price at 1.25/2.50 is about 2.3x
    the tick cost. A cached price of 0.20 brings the ledger onto that tick cost.
    The reservation still uses the full input price and does not see the cache.
    """
    usage = {
        "prompt_tokens": 35629,
        "completion_tokens": 716,
        "prompt_tokens_details": {"cached_tokens": 24576},
    }
    full = input_cost_usd(35629, 24576, 1.25, None) + 716 / 1_000_000 * 2.50
    discounted = input_cost_usd(35629, 24576, 1.25, 0.20) + 716 / 1_000_000 * 2.50
    assert round(full, 8) == 0.04632625
    assert round(discounted, 8) == 0.02052145
    assert full / 0.0205215 == pytest.approx(2.3, abs=0.05)

    transport = FakeTransport(
        {
            "choices": [{"message": {"content": "ok", "tool_calls": []}}],
            "usage": usage,
        }
    )
    ledger = SpendLedger(tmp_path / "ledger.jsonl")
    provider = LiveProvider(
        _settings(
            llm_price_in_per_mtok=1.25,
            llm_price_out_per_mtok=2.50,
            llm_price_cached_per_mtok=0.20,
            max_live_spend_usd=1.0,
            llm_max_output_tokens=800,
        ),
        transport,
        ledger,
    )
    provider.complete(_request("hello"))
    assert ledger.rows[0]["cached_tokens"] == 24576
    assert ledger.rows[0]["cost_usd"] == round(discounted, 8)

    plain = LiveProvider(
        _settings(
            llm_price_in_per_mtok=1.25,
            llm_price_out_per_mtok=2.50,
            max_live_spend_usd=1.0,
            llm_max_output_tokens=800,
        ),
        FakeTransport(
            {
                "choices": [{"message": {"content": "ok", "tool_calls": []}}],
                "usage": usage,
            }
        ),
        SpendLedger(tmp_path / "plain.jsonl"),
    )
    plain.complete(_request("hello"))
    assert plain.ledger.rows[0]["cost_usd"] == round(full, 8)


def test_transport_errors_are_redacted(tmp_path: Path) -> None:
    transport = FakeTransport(error=RuntimeError("auth failed " + KEY))
    ledger = SpendLedger(tmp_path / "ledger.jsonl")
    provider = LiveProvider(_settings(), transport, ledger)
    with pytest.raises(ProviderError) as exc:
        provider.complete(_request())
    assert KEY not in str(exc.value)
    assert transport.calls == 1


def test_token_cap_and_reported_usage(tmp_path: Path) -> None:
    transport = FakeTransport()
    settings = _settings(
        llm_price_in_per_mtok=None,
        llm_price_out_per_mtok=None,
        max_live_tokens=1,
        llm_max_output_tokens=1000,
    )
    provider = LiveProvider(settings, transport, SpendLedger(tmp_path / "a.jsonl"))
    with pytest.raises(SpendCapError):
        provider.complete(_request())
    assert transport.calls == 0

    huge = FakeTransport(
        {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 5_000_000, "completion_tokens": 1},
        }
    )
    priced = LiveProvider(
        _settings(max_live_spend_usd=0.01, llm_max_output_tokens=1),
        huge,
        SpendLedger(tmp_path / "b.jsonl"),
    )
    # A short request reserves little; the reported usage then crosses the cap.
    if estimate_tokens("x") >= 0:
        try:
            priced.complete(_request("hi"))
        except SpendCapError:
            assert huge.calls == 1
            assert priced.ledger.rows[0]["cost_status"] == "computed"
        else:
            pytest.fail("reported usage should have crossed the spend cap")


def test_urllib_transport_uses_injected_opener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        def read(self) -> bytes:
            return b'{"choices": []}'

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

    def fake_urlopen(_request: object, timeout: float = 0) -> FakeResponse:
        assert timeout == 5
        return FakeResponse()

    monkeypatch.setattr("scheduling_agent.live.urlopen", fake_urlopen)
    body = UrllibTransport().post("https://llm.example/v1/chat/completions", {}, {}, 5)
    assert body == {"choices": []}

    def broken(_request: object, timeout: float = 0) -> FakeResponse:
        raise OSError("down " + KEY)

    monkeypatch.setattr("scheduling_agent.live.urlopen", broken)
    with pytest.raises(ProviderError) as exc:
        UrllibTransport().post("https://llm.example", {}, {}, 5)
    assert KEY not in str(exc.value)


class _ArrayBody:
    def read(self) -> bytes:
        return b"[]"

    def __enter__(self) -> _ArrayBody:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


def _array_response() -> _ArrayBody:
    return _ArrayBody()


def test_urllib_rejects_a_non_object(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scheduling_agent.live.urlopen", lambda *_a, **_k: _array_response()
    )
    with pytest.raises(ProviderError):
        UrllibTransport().post("https://llm.example/chat/completions", {}, {}, 5)


def test_chat_url_and_bad_payloads(tmp_path: Path) -> None:
    assert (
        chat_url("https://llm.example/v1/") == "https://llm.example/v1/chat/completions"
    )
    assert chat_url("https://llm.example/v1/chat/completions") == (
        "https://llm.example/v1/chat/completions"
    )
    transport = FakeTransport({"choices": []})
    provider = LiveProvider(_settings(), transport, SpendLedger(tmp_path / "c.jsonl"))
    with pytest.raises(ProviderError):
        provider.complete(CompletionRequest(messages=[], tools=[]))
    bad_args = FakeTransport(
        {
            "choices": [
                {
                    "message": {
                        "tool_calls": [{"function": {"name": "x", "arguments": 3}}]
                    }
                }
            ]
        }
    )
    provider = LiveProvider(_settings(), bad_args, SpendLedger(tmp_path / "d.jsonl"))
    parsed = provider.complete(_request("a"))
    assert parsed.tool_calls[0].parse_error == "invalid_json"
