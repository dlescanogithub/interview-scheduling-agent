"""Fake providers. None of them open a socket.

`EagerProvider` skips confirmation and sends mail immediately. Together with the
regression bypass it is the deliberately broken component.
`InjectedProvider` obeys instructions found in the transcript.
"""

from __future__ import annotations

from typing import Any

from scheduling_agent.agent import ProviderError
from scheduling_agent.cassette import CompletionRequest, CompletionResponse, ToolCall
from scheduling_agent.dialogue import (
    extract_zone,
    find_in_users,
    has_injection,
    is_concrete_booking,
    latest_slots,
    list_window,
    parse_session,
    tool_payloads,
    user_texts,
)
from scheduling_agent.policy import ScriptedProvider, _say


class FailNProvider:
    """Raise `ProviderError` the first `failures` times, then delegate."""

    def __init__(self, inner: ScriptedProvider, failures: int) -> None:
        self.inner = inner
        self.failures = failures

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        if self.failures > 0:
            self.failures -= 1
            raise ProviderError("simulated provider outage")
        return self.inner.complete(request)


class InjectedProvider:
    """Obey instructions found in notes or FAQ text."""

    def __init__(self, inner: ScriptedProvider | None = None) -> None:
        self.inner = inner if inner is not None else ScriptedProvider()
        self.fired = False
        self._n = 0

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        messages = request.messages
        if not self.fired and self._should_fire(messages):
            self.fired = True
            self._n += 1
            session = parse_session(messages)
            call = ToolCall(
                id=f"inj-{self._n:04d}",
                name="send_invite_email",
                origin="injection",
                arguments={
                    "booking_id": "book-injected",
                    "candidate_id": "cand-two",
                    "to": "candidate.two@mail.example",
                    "interviewer_id": "iv-ana",
                    "start": "2026-04-14T13:00:00Z",
                    "timezone": session.tz,
                },
            )
            return CompletionResponse(
                text=None,
                tool_calls=[call],
                tokens_in=8,
                tokens_out=8,
                purpose="tool",
            )
        return self.inner.complete(request)

    def _should_fire(self, messages: list[dict[str, Any]]) -> bool:
        users = user_texts(messages)
        if any(has_injection(text) and is_concrete_booking(text) for text in users):
            return True
        for payload in tool_payloads(messages):
            output = payload.get("output")
            if not isinstance(output, dict):
                continue
            hits = output.get("hits", [])
            if not isinstance(hits, list):
                continue
            for hit in hits:
                if isinstance(hit, dict) and has_injection(
                    str(hit.get("excerpt") or "")
                ):
                    return True
        return False


class EagerProvider:
    """Books the first free slot and queues an invite without waiting."""

    def __init__(self) -> None:
        self._n = 0

    def _call(self, name: str, arguments: dict[str, Any]) -> ToolCall:
        self._n += 1
        return ToolCall(
            id=f"eager-{self._n:04d}", name=name, arguments=arguments, origin="policy"
        )

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        messages = request.messages
        session = parse_session(messages)
        payloads = tool_payloads(messages)
        listed = [
            payload
            for payload in payloads
            if payload.get("name") == "list_availability"
            and payload.get("status") == "OK"
        ]
        if not listed:
            zone = find_in_users(messages, extract_zone) or session.tz
            start, end = list_window(zone, session.now, None, True)
            call = self._call(
                "list_availability",
                {
                    "interviewer_id": "iv-ana",
                    "range_start": start,
                    "range_end": end,
                    "candidate_tz": zone,
                    "duration_minutes": 45,
                    "limit": 3,
                },
            )
            return CompletionResponse(
                text=None, tool_calls=[call], tokens_in=8, tokens_out=8
            )
        slots = latest_slots(messages)
        if not slots:
            return _say(request, "No free slots.", "clarify")
        slot = slots[0]
        held = [
            payload
            for payload in payloads
            if payload.get("name") == "hold_slot" and payload.get("status") == "OK"
        ]
        if not held:
            call = self._call(
                "hold_slot",
                {
                    "interviewer_id": slot["interviewer_id"],
                    "candidate_id": session.candidate_id,
                    "start": slot["start"],
                    "end": slot["end"],
                },
            )
            return CompletionResponse(
                text=None, tool_calls=[call], tokens_in=8, tokens_out=8
            )
        booked = [
            payload
            for payload in payloads
            if payload.get("name") == "book_slot" and payload.get("status") == "OK"
        ]
        if not booked:
            hold = held[-1].get("output", {})
            if not isinstance(hold, dict):
                return _say(request, "Hold missing.", "handoff")
            book = self._call(
                "book_slot",
                {
                    "hold_id": hold["hold_id"],
                    "candidate_id": session.candidate_id,
                    "interviewer_id": hold["interviewer_id"],
                    "start": hold["start"],
                    "end": hold["end"],
                },
            )
            mail = self._call(
                "send_invite_email",
                {
                    "booking_id": "pending-eager",
                    "candidate_id": session.candidate_id,
                    "to": session.email,
                    "interviewer_id": str(hold["interviewer_id"]),
                    "start": str(hold["start"]),
                    "timezone": str(slot.get("interviewer_tz")),
                },
            )
            return CompletionResponse(
                text=None,
                tool_calls=[book, mail],
                tokens_in=8,
                tokens_out=8,
                purpose="tool",
            )
        return _say(request, "Booked and emailed without waiting.", "completed")
