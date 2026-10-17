"""OpenAI-compatible live adapter. Off unless LIVE_LLM=1. Never used by CI.

Prices come only from the environment. The API key is redacted from errors,
logs and the JSONL ledger.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any, Protocol
from urllib.request import Request, urlopen

from scheduling_agent.agent import ProviderError, SpendCapError
from scheduling_agent.cassette import CompletionRequest, CompletionResponse, ToolCall
from scheduling_agent.clock import Clock, WallClock
from scheduling_agent.config import Settings, assert_live_ready
from scheduling_agent.logging_setup import configure_logging, log_event, redact


class Transport(Protocol):
    def post(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        """Return the decoded JSON body. Implementations must not log `headers`."""


class UrllibTransport:
    """Real HTTP transport. Tests inject a fake instead of constructing this."""

    def post(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        encoded = json.dumps(body).encode("utf-8")
        request = Request(url, data=encoded, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310
                raw = response.read().decode("utf-8")
        except Exception as exc:
            raise ProviderError(redact(str(exc))) from None
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ProviderError("live response was not an object")
        return parsed


def chat_url(base: str) -> str:
    trimmed = base.rstrip("/")
    if trimmed.endswith("/chat/completions"):
        return trimmed
    return trimmed + "/chat/completions"


def estimate_tokens(text: str) -> int:
    """Rough reservation size. It is an upper-bound input, not a measurement."""
    return max(1, (len(text) + 3) // 4)


@dataclass
class SpendLedger:
    path: Path
    spent_usd: float = 0.0
    spent_tokens: int = 0
    rows: list[dict[str, Any]] = field(default_factory=list)

    def append(self, row: dict[str, Any]) -> None:
        self.rows.append(row)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


class LiveProvider:
    """Chat-completions tool calling with a hard spend cap."""

    def __init__(
        self,
        settings: Settings,
        transport: Transport,
        ledger: SpendLedger,
        clock: Clock | None = None,
    ) -> None:
        assert_live_ready(settings)
        self.settings = settings
        self.transport = transport
        self.ledger = ledger
        self.clock = clock if clock is not None else WallClock()
        self._n = 0

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        settings = self.settings
        blob = json.dumps(request.messages, ensure_ascii=False, default=str)
        est_in = estimate_tokens(blob) * 2
        max_out = settings.llm_max_output_tokens
        prices = (
            settings.llm_price_in_per_mtok is not None
            and settings.llm_price_out_per_mtok is not None
        )
        if prices:
            pin = float(settings.llm_price_in_per_mtok or 0)
            pout = float(settings.llm_price_out_per_mtok or 0)
            reserve = est_in / 1_000_000 * pin + max_out / 1_000_000 * pout
            cap = float(settings.max_live_spend_usd or 0)
            if self.ledger.spent_usd + reserve > cap:
                raise SpendCapError("reservation would exceed MAX_LIVE_SPEND_USD")
        else:
            reserve_tokens = est_in + max_out
            cap_tokens = int(settings.max_live_tokens or 0)
            if self.ledger.spent_tokens + reserve_tokens > cap_tokens:
                raise SpendCapError("reservation would exceed MAX_LIVE_TOKENS")
        url = chat_url(settings.llm_base_url)
        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": request.model or settings.scheduler_model(),
            "messages": _openai_messages(request.messages),
            "tools": request.tools,
            "max_tokens": max_out,
        }
        try:
            payload = self.transport.post(url, headers, body, timeout=60)
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(redact(str(exc))) from None
        text, calls = _parse_message(payload, self._next_id)
        raw_usage = payload.get("usage")
        usage: dict[str, Any] = raw_usage if isinstance(raw_usage, dict) else {}
        tokens_in = int(usage.get("prompt_tokens") or est_in)
        tokens_out = int(usage.get("completion_tokens") or 0)
        cost_status = "computed" if prices else "unknown"
        cost = 0.0
        if prices:
            pin = float(settings.llm_price_in_per_mtok or 0)
            pout = float(settings.llm_price_out_per_mtok or 0)
            cost = tokens_in / 1_000_000 * pin + tokens_out / 1_000_000 * pout
            self.ledger.spent_usd += cost
        self.ledger.spent_tokens += tokens_in + tokens_out
        row = {
            "ts": self.clock.now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "model": request.model or settings.scheduler_model(),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": None if cost_status == "unknown" else round(cost, 8),
            "cost_status": cost_status,
        }
        self.ledger.append(row)
        log_event(
            configure_logging(),
            20,
            "live_call",
            "live",
            model=row["model"],
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_status=cost_status,
        )
        if prices and self.ledger.spent_usd > float(settings.max_live_spend_usd or 0):
            raise SpendCapError("reported usage exceeded MAX_LIVE_SPEND_USD")
        if not prices and self.ledger.spent_tokens > int(settings.max_live_tokens or 0):
            raise SpendCapError("reported usage exceeded MAX_LIVE_TOKENS")
        return CompletionResponse(
            text=text,
            tool_calls=calls,
            tokens_in=tokens_in,
            tokens_out=max(tokens_out, 1),
            purpose="talk" if calls else _live_purpose(request.messages),
        )

    def _next_id(self) -> str:
        self._n += 1
        return f"live-{self._n:04d}"


_EXTERNAL_TOOLS = {
    "send_invite_email",
    "send_reschedule_email",
    "send_cancellation_notice",
}


def _live_purpose(messages: list[dict[str, Any]]) -> str:
    """A live model cannot set purpose. The latest external tool result does.

    A finished invite is `completed`. A send still waiting on the recruiter is
    `pending_approval`. Reads, holds, and bookings leave the turn as talk.
    """
    for message in reversed(messages):
        if str(message.get("role") or "") != "tool":
            continue
        try:
            loaded = json.loads(str(message.get("content") or ""))
        except json.JSONDecodeError:
            continue
        if not isinstance(loaded, dict):
            continue
        name = str(loaded.get("name") or "")
        status = str(loaded.get("status") or "")
        if status == "PENDING_APPROVAL":
            return "pending_approval"
        if (
            name in _EXTERNAL_TOOLS
            and status == "OK"
            and loaded.get("executed") is True
        ):
            return "completed"
    return "talk"


def _openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    exported: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role") or "user")
        if role == "tool":
            exported.append(
                {
                    "role": "tool",
                    "tool_call_id": str(message.get("name") or "tool"),
                    "content": str(message.get("content") or ""),
                }
            )
            continue
        calls = message.get("tool_calls")
        if role == "assistant" and isinstance(calls, list) and calls:
            exported.append(
                {
                    "role": "assistant",
                    "content": message.get("content") or "",
                    "tool_calls": [
                        {
                            "id": str(call.get("id")),
                            "type": "function",
                            "function": {
                                "name": call.get("name"),
                                "arguments": json.dumps(call.get("arguments", {})),
                            },
                        }
                        for call in calls
                        if isinstance(call, dict)
                    ],
                }
            )
            continue
        exported.append({"role": role, "content": str(message.get("content") or "")})
    return exported


def _parse_message(
    payload: dict[str, Any],
    next_id: Any,
) -> tuple[str | None, list[ToolCall]]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ProviderError("live response has no choices")
    message = choices[0].get("message", {})
    if not isinstance(message, dict):
        raise ProviderError("live response message missing")
    content = message.get("content")
    text = content if isinstance(content, str) and content else None
    calls: list[ToolCall] = []
    raw_calls = message.get("tool_calls") or []
    if isinstance(raw_calls, list):
        for raw in raw_calls:
            if not isinstance(raw, dict):
                continue
            function = raw.get("function", {})
            if not isinstance(function, dict):
                continue
            arguments = function.get("arguments") or "{}"
            parse_error: str | None = None
            parsed: dict[str, Any] = {}
            if isinstance(arguments, str):
                try:
                    loaded = json.loads(arguments)
                except json.JSONDecodeError:
                    loaded = None
                    parse_error = "invalid_json"
                if parse_error is None and isinstance(loaded, dict):
                    parsed = loaded
                elif parse_error is None:
                    parse_error = "invalid_json"
            elif isinstance(arguments, dict):
                parsed = arguments
            else:
                parse_error = "invalid_json"
            calls.append(
                ToolCall(
                    id=str(raw.get("id") or next_id()),
                    name=str(function.get("name") or "unknown"),
                    arguments=parsed,
                    origin="policy",
                    parse_error=parse_error,
                )
            )
    return text, calls
