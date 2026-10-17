"""Deterministic cassette provider.

Responses are keyed by a hash of the normalized request. A missing entry is an
error. This type never opens a socket.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    origin: str = "policy"
    parse_error: str | None = None


@dataclass
class CompletionRequest:
    messages: list[dict[str, Any]]
    tools: list[dict[str, Any]]
    model: str | None = None


@dataclass
class CompletionResponse:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_in: int = 1
    tokens_out: int = 1
    purpose: str = "talk"
    citations: list[str] = field(default_factory=list)
    unknown: bool = False


class CassetteMiss(KeyError):
    """No recorded response for this request. A silent network call is forbidden."""


def request_key(request: CompletionRequest) -> str:
    """Hash the normalized request. Key order does not change the digest."""
    normalized = {
        "messages": request.messages,
        "model": request.model,
        "tools": request.tools,
    }
    blob = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class CassetteProvider:
    """Replay recorded completions. Missing keys raise `CassetteMiss`."""

    def __init__(self, entries: dict[str, CompletionResponse]) -> None:
        self.entries = entries

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        key = request_key(request)
        try:
            return self.entries[key]
        except KeyError as exc:
            raise CassetteMiss(key) from exc
