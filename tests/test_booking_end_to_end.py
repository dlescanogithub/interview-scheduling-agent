"""End-to-end live booking, and the cuts that stay INCOMPLETE. No socket."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest

from scheduling_agent.cli import main
from scheduling_agent.dialogue import format_slot_line

LIST_ARGS = {
    "interviewer_id": "iv-ana",
    "range_start": "2026-04-14T12:00:00Z",
    "range_end": "2026-04-15T00:00:00Z",
    "candidate_tz": "America/Argentina/Buenos_Aires",
    "duration_minutes": 45,
    "limit": 3,
}
_EMAIL = "candidata.uno@mail.example"


def _call(name: str, arguments: dict[str, Any], call_id: str) -> dict[str, Any]:
    return {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "function": {
                                "name": name,
                                "arguments": json.dumps(arguments),
                            },
                        }
                    ],
                }
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10},
    }


def _text(body: str) -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": body}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 8},
    }


def _payloads(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") != "tool":
            continue
        loaded = json.loads(str(message.get("content") or ""))
        if isinstance(loaded, dict):
            found.append(loaded)
    return found


def _ok(payloads: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for payload in reversed(payloads):
        if (
            payload.get("name") == name
            and payload.get("status") == "OK"
            and payload.get("executed") is True
        ):
            return payload
    return None


class FlowTransport:
    """Canned live model. The first yes holds. The exact yes books."""

    book = True

    def __init__(self) -> None:
        self.bodies: list[dict[str, Any]] = []

    def post(
        self,
        _url: str,
        _headers: dict[str, str],
        body: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        self.bodies.append(body)
        assert timeout == 60
        assert "sk-" not in json.dumps(body)
        return self._next(body["messages"])

    def _next(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        payloads = _payloads(messages)
        users = [
            str(message.get("content") or "")
            for message in messages
            if message.get("role") == "user"
        ]
        exact = any("horario exacto" in text for text in users)
        recruiter = any(
            message.get("role") == "system"
            and str(message.get("content") or "").startswith("recruiter_decision=")
            for message in messages
        )
        listed = _ok(payloads, "list_availability")
        if listed is None:
            return _call("list_availability", LIST_ARGS, "call-list")
        output = listed.get("output")
        slots = output.get("slots") if isinstance(output, dict) else None
        if not isinstance(slots, list) or not slots:
            return _text("No tengo horarios libres. No reservé nada.")
        lines = [
            format_slot_line(index, slot, "es")
            for index, slot in enumerate(slots, start=1)
            if isinstance(slot, dict)
        ]
        offered = any(
            message.get("role") == "assistant"
            and "ART, UTC-3" in str(message.get("content") or "")
            for message in messages
        )
        if not offered:
            offer = "Puedo ofrecerte estas opciones.\n" + "\n".join(lines)
            offer += "\nRespondé sí para confirmar la opción 1."
            return _text(offer)
        slot = slots[0]
        held = _ok(payloads, "hold_slot")
        if held is None:
            return _call(
                "hold_slot",
                {
                    "interviewer_id": slot["interviewer_id"],
                    "candidate_id": "cand-uno",
                    "start": slot["start"],
                    "end": slot["end"],
                },
                "call-hold",
            )
        if not exact or not FlowTransport.book:
            if not exact:
                return _text(
                    "Dejé la opción 1 en hold. Para reservar, confirmá ese horario.\n"
                    + lines[0]
                )
            return _text("No reservé nada.")
        booked = _ok(payloads, "book_slot")
        if booked is None:
            hold_out = held.get("output")
            hold_id = hold_out.get("hold_id") if isinstance(hold_out, dict) else ""
            return _call(
                "book_slot",
                {
                    "hold_id": hold_id,
                    "candidate_id": "cand-uno",
                    "interviewer_id": slot["interviewer_id"],
                    "start": slot["start"],
                    "end": slot["end"],
                },
                "call-book",
            )
        sent = _ok(payloads, "send_invite_email")
        pending = any(
            payload.get("name") == "send_invite_email"
            and payload.get("status") == "PENDING_APPROVAL"
            for payload in payloads
        )
        if sent is None and not recruiter:
            if pending:
                return _text(
                    "Quedó reservado.\n"
                    + lines[0]
                    + "\nFalta la aprobación del recruiter. No envié el correo."
                )
            book_out = booked.get("output")
            booking_id = ""
            if isinstance(book_out, dict):
                booking_id = str(book_out.get("booking_id") or "")
            return _call(
                "send_invite_email",
                {
                    "booking_id": booking_id,
                    "candidate_id": "cand-uno",
                    "to": _EMAIL,
                    "interviewer_id": slot["interviewer_id"],
                    "start": slot["start"],
                    "timezone": "America/Argentina/Buenos_Aires",
                },
                "call-mail",
            )
        if recruiter and sent is None:
            book_out = booked.get("output")
            booking_id = ""
            if isinstance(book_out, dict):
                booking_id = str(book_out.get("booking_id") or "")
            return _call(
                "send_invite_email",
                {
                    "booking_id": booking_id,
                    "candidate_id": "cand-uno",
                    "to": _EMAIL,
                    "interviewer_id": slot["interviewer_id"],
                    "start": slot["start"],
                    "timezone": "America/Argentina/Buenos_Aires",
                },
                "call-mail-approved",
            )
        return _text(
            "Listo. El correo quedó en la bandeja de salida después de la aprobación."
        )


@pytest.fixture(autouse=True)
def _drop_live_log_handler() -> Iterator[None]:
    """The live adapter logs to stderr. Drop that handler after each test.

    configure_logging binds whatever stderr is current. Under pytest that
    buffer closes when the test ends, and a later test would then fail to
    parse a logging error.
    """
    yield
    logger = logging.getLogger("scheduling_agent")
    logger.handlers.clear()


def _live_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVE_LLM", "1")
    monkeypatch.setenv("MAX_LIVE_SPEND_USD", "1")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("LLM_API_KEY", "sk" + "-" + "cassette" + "only")
    monkeypatch.setenv("LLM_MODEL", "lab-model")
    monkeypatch.setenv("LLM_PRICE_IN_PER_MTOK", "0")
    monkeypatch.setenv("LLM_PRICE_OUT_PER_MTOK", "0")
    monkeypatch.setattr("scheduling_agent.cli.UrllibTransport", FlowTransport)


def _tools(transcript: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for line in transcript.splitlines():
        if line.startswith("[tool] "):
            found.append(json.loads(line[len("[tool] ") :]))
    return found


def test_live_end_to_end_books_only_after_the_exact_yes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _live_env(monkeypatch)
    FlowTransport.book = True
    code = main(["live", "--scenario", "booking_end_to_end", "--max-turns", "12"])
    out = capsys.readouterr().out
    assert code == 0
    assert "invariants_passed=true" in out
    assert "task_completed=true" in out
    assert "live result: PASS" in out
    assert "live result: INCOMPLETE" not in out
    tools = _tools(out)
    book_at = next(
        index
        for index, payload in enumerate(tools)
        if payload.get("name") == "book_slot" and payload.get("executed") is True
    )
    sends = [payload for payload in tools if payload.get("name") == "send_invite_email"]
    assert sends[0]["status"] == "PENDING_APPROVAL"
    assert sends[0]["executed"] is False
    assert sends[-1]["status"] == "OK"
    assert sends[-1]["executed"] is True
    exact_at = out.index("Sí, confirmo ese horario exacto.")
    book_line = out.index('"name": "book_slot"')
    assert exact_at < book_line
    sent_at = next(
        index
        for index, payload in enumerate(tools)
        if payload.get("name") == "send_invite_email"
        and payload.get("executed") is True
    )
    assert book_at < sent_at


def test_live_end_to_end_without_a_booking_is_incomplete(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _live_env(monkeypatch)
    FlowTransport.book = False
    code = main(["live", "--scenario", "booking_end_to_end", "--max-turns", "12"])
    out = capsys.readouterr().out
    assert code == 3
    assert "invariants_passed=true" in out
    assert "task_completed=false" in out
    assert "live result: INCOMPLETE" in out
    assert "live result: PASS" not in out
    assert all(
        not (payload.get("name") == "book_slot" and payload.get("executed") is True)
        for payload in _tools(out)
    )


def test_happy_path_live_still_incomplete_without_the_second_yes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _live_env(monkeypatch)
    FlowTransport.book = True
    code = main(["live", "--scenario", "happy_path", "--max-turns", "12"])
    out = capsys.readouterr().out
    assert code == 3
    assert "invariants_passed=true" in out
    assert "task_completed=false" in out
    assert "live result: INCOMPLETE" in out
    assert "horario exacto" not in out
    assert all(
        not (payload.get("name") == "book_slot" and payload.get("executed") is True)
        for payload in _tools(out)
    )
