"""Scripted policy used as the agent brain in CI.

It is a small state machine over the transcript. It is not a model and it does
not score model quality.
"""

from __future__ import annotations

import json
from typing import Any

from scheduling_agent.cassette import CompletionRequest, CompletionResponse, ToolCall
from scheduling_agent.dialogue import (
    SessionView,
    booking_slot_view,
    boundary_index,
    detect_lang,
    extract_clock,
    extract_date,
    extract_interviewer,
    extract_zone,
    find_in_users,
    format_slot_line,
    goal_of,
    has_concrete_date,
    has_injection,
    is_ambiguous_tuesday,
    is_cancel_action,
    is_concrete_booking,
    is_faq,
    is_handoff,
    is_ood,
    is_refusal,
    is_reschedule_action,
    is_schedule_action,
    is_yes,
    last_user_text,
    latest_slots,
    list_window,
    mentions_other,
    next_tuesdays,
    option_index,
    own_booking,
    parse_session,
    previous_call_args,
    proposal_text,
    recruiter_decision,
    select_slot,
    tool_payloads,
    user_texts,
    zone_phrase,
)
from scheduling_agent.roster import INTERVIEWERS, other_markers


def _usage(
    request: CompletionRequest, text: str, calls: list[ToolCall]
) -> tuple[int, int]:
    """Simulated token counts from character length. Not a measured model cost."""
    blob = json.dumps(
        {"messages": request.messages, "tools": [call.name for call in calls]},
        ensure_ascii=False,
        default=str,
    )
    return max(1, len(blob) // 4), max(1, len(text) // 4)


def _say(
    request: CompletionRequest,
    text: str,
    purpose: str,
    *,
    citations: list[str] | None = None,
    unknown: bool = False,
) -> CompletionResponse:
    tokens_in, tokens_out = _usage(request, text, [])
    return CompletionResponse(
        text=text,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        purpose=purpose,
        citations=citations or [],
        unknown=unknown,
    )


class ScriptedProvider:
    """Deterministic tool-calling policy for repeatable scenario runs."""

    def __init__(self) -> None:
        self._n = 0

    def _call(
        self, name: str, arguments: dict[str, Any], origin: str = "policy"
    ) -> ToolCall:
        self._n += 1
        return ToolCall(
            id=f"call-{self._n:04d}", name=name, arguments=arguments, origin=origin
        )

    def _tools(
        self, request: CompletionRequest, calls: list[ToolCall]
    ) -> CompletionResponse:
        tokens_in, tokens_out = _usage(request, "", calls)
        return CompletionResponse(
            text=None,
            tool_calls=calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            purpose="tool",
        )

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        messages = request.messages
        session = parse_session(messages)
        lang = detect_lang(last_user_text(messages), session.lang)
        after = boundary_index(messages)
        payloads = [
            payload
            for payload in tool_payloads(messages, after=after)
            if not (
                payload.get("origin") == "injection"
                and payload.get("status") == "REFUSED"
            )
        ]
        if payloads:
            chained = self._from_tools(request, messages, session, lang, payloads)
            if chained is not None:
                return chained
        decision = recruiter_decision(messages)
        if decision is not None and not payloads:
            return self._from_recruiter(request, messages, session, lang, decision)
        return self._from_user(request, messages, session, lang)

    def _from_recruiter(
        self,
        request: CompletionRequest,
        messages: list[dict[str, Any]],
        session: SessionView,
        lang: str,
        decision: dict[str, str],
    ) -> CompletionResponse:
        if decision.get("recruiter_decision") == "reject":
            return _say(request, _copy(lang, "rejected"), "rejected")
        tool_name = decision.get("tool", "")
        arguments = previous_call_args(messages, tool_name)
        if arguments is None:
            return _say(request, _copy(lang, "handoff"), "handoff")
        return self._tools(request, [self._call(tool_name, arguments)])

    def _from_tools(
        self,
        request: CompletionRequest,
        messages: list[dict[str, Any]],
        session: SessionView,
        lang: str,
        payloads: list[dict[str, Any]],
    ) -> CompletionResponse | None:
        last = payloads[-1]
        name = str(last.get("name"))
        status = str(last.get("status"))
        raw_output = last.get("output")
        output: dict[str, Any] = raw_output if isinstance(raw_output, dict) else {}
        if status == "PENDING_APPROVAL":
            return _say(request, _copy(lang, "pending"), "pending_approval")
        if status == "KILL_SWITCH":
            return _say(request, _copy(lang, "kill"), "info")
        if status == "REJECTED":
            return _say(request, _copy(lang, "rejected"), "rejected")
        if status == "EXPIRED":
            return _say(request, _copy(lang, "expired"), "clarify")
        if status == "NEEDS_CONFIRMATION":
            return _say(request, _copy(lang, "need_yes"), "confirm_request")
        if status == "REFUSED":
            return _say(request, _copy(lang, "other"), "refusal")
        if status == "BUDGET_EXCEEDED":
            return _say(request, _copy(lang, "handoff"), "handoff")
        if status in {"HOLD_EXPIRED", "SLOT_TAKEN"} or (
            name == "book_slot" and status == "HOLD_EXPIRED"
        ):
            return self._recover_slot(request, messages, session, lang, status)
        if name == "list_availability" and status == "OK":
            return self._after_list(request, messages, session, lang, output)
        if name == "hold_slot" and status == "OK":
            return self._book_from_hold(request, messages, output)
        if name == "book_slot" and status == "OK":
            return self._after_book(request, messages, session, output)
        if name == "cancel_booking" and status == "OK":
            return self._after_cancel(request, messages, session, output)
        if name in {
            "send_invite_email",
            "send_reschedule_email",
            "send_cancellation_notice",
        }:
            if status == "OK":
                key = "cancelled_done" if name == "send_cancellation_notice" else "done"
                return _say(request, _copy(lang, key), "completed")
        if name == "get_booking" and status == "OK":
            return self._after_lookup(request, messages, session, lang)
        if name == "search_faq" and status == "OK":
            return self._after_faq(request, messages, session, lang, output)
        if name == "release_hold" and status == "OK":
            return _say(request, _copy(lang, "refused"), "refusal")
        if status != "OK":
            return _say(request, _copy(lang, "handoff"), "handoff")
        return None

    def _recover_slot(
        self,
        request: CompletionRequest,
        messages: list[dict[str, Any]],
        session: SessionView,
        lang: str,
        status: str,
    ) -> CompletionResponse:
        relisted = [
            payload
            for payload in tool_payloads(messages, after=boundary_index(messages))
            if payload.get("name") == "list_availability"
            and payload.get("status") == "OK"
        ]
        if status == "SLOT_TAKEN" and not relisted:
            return self._list(request, messages, session, widened=True)
        slots = latest_slots(messages)
        if status == "HOLD_EXPIRED":
            hold = _last_output(messages, "hold_slot")
            if hold is not None:
                matched = [
                    slot
                    for slot in slots
                    if slot.get("start") == hold.get("start")
                    and slot.get("end") == hold.get("end")
                ]
                slots = matched or slots[:1]
            intro = _copy(lang, "expired_hold")
            purpose = "confirm_request"
        else:
            intro = _copy(lang, "taken")
            purpose = "proposal"
        if not slots:
            return _say(request, _copy(lang, "none"), "handoff")
        text = proposal_text(lang, slots[:3], intro=intro)
        return _say(request, text, purpose)

    def _after_list(
        self,
        request: CompletionRequest,
        messages: list[dict[str, Any]],
        session: SessionView,
        lang: str,
        output: dict[str, Any],
    ) -> CompletionResponse:
        slots = output.get("slots")
        widened = bool(output.get("widened"))
        if not isinstance(slots, list) or not slots:
            if not widened:
                return self._list(request, messages, session, widened=True)
            return _say(request, _copy(lang, "none"), "handoff")
        typed = [slot for slot in slots if isinstance(slot, dict)]
        preferred = find_in_users(messages, extract_clock)
        zone = str(typed[0].get("interviewer_tz"))
        missed = preferred is not None and all(
            slot.get("local_start") != preferred for slot in typed
        )
        if missed:
            intro = _intro_miss(lang, str(preferred), zone)
        elif goal_of(messages) == "reschedule":
            intro = _copy(lang, "reschedule_offer")
        else:
            intro = _copy(lang, "offer")
        purpose = (
            "confirm_reschedule" if goal_of(messages) == "reschedule" else "proposal"
        )
        return _say(request, proposal_text(lang, typed[:3], intro=intro), purpose)

    def _book_from_hold(
        self,
        request: CompletionRequest,
        messages: list[dict[str, Any]],
        output: dict[str, Any],
    ) -> CompletionResponse:
        arguments = {
            "hold_id": output["hold_id"],
            "candidate_id": output["candidate_id"],
            "interviewer_id": output["interviewer_id"],
            "start": output["start"],
            "end": output["end"],
        }
        return self._tools(request, [self._call("book_slot", arguments)])

    def _after_book(
        self,
        request: CompletionRequest,
        messages: list[dict[str, Any]],
        session: SessionView,
        output: dict[str, Any],
    ) -> CompletionResponse:
        if goal_of(messages) == "reschedule":
            previous = own_booking(messages)
            if previous is not None and not _cancelled(messages, str(previous["id"])):
                return self._tools(
                    request,
                    [
                        self._call(
                            "cancel_booking",
                            {
                                "booking_id": previous["id"],
                                "candidate_id": session.candidate_id,
                            },
                        )
                    ],
                )
        return self._send(request, session, "send_invite_email", output)

    def _after_cancel(
        self,
        request: CompletionRequest,
        messages: list[dict[str, Any]],
        session: SessionView,
        output: dict[str, Any],
    ) -> CompletionResponse:
        tool_name = (
            "send_reschedule_email"
            if goal_of(messages) == "reschedule"
            else "send_cancellation_notice"
        )
        newest = (
            _last_output(messages, "book_slot")
            if tool_name == "send_reschedule_email"
            else output
        )
        source = newest or output
        return self._send(request, session, tool_name, source)

    def _send(
        self,
        request: CompletionRequest,
        session: SessionView,
        tool_name: str,
        source: dict[str, Any],
    ) -> CompletionResponse:
        interviewer_id = str(
            source.get("interviewer_id")
            or find_in_users(request.messages, extract_interviewer)
            or "iv-ana"
        )
        zone = INTERVIEWERS[interviewer_id]["timezone"]
        arguments = {
            "booking_id": str(source.get("booking_id") or source.get("id")),
            "candidate_id": session.candidate_id,
            "to": session.email,
            "interviewer_id": interviewer_id,
            "start": str(source["start"]),
            "timezone": zone,
        }
        return self._tools(request, [self._call(tool_name, arguments)])

    def _after_lookup(
        self,
        request: CompletionRequest,
        messages: list[dict[str, Any]],
        session: SessionView,
        lang: str,
    ) -> CompletionResponse:
        booking = own_booking(messages)
        if booking is None:
            return _say(request, _copy(lang, "no_booking"), "clarify")
        if goal_of(messages) == "reschedule":
            if not latest_slots(messages):
                return self._list(request, messages, session, widened=True)
            return self._after_list(
                request,
                messages,
                session,
                lang,
                {"slots": latest_slots(messages), "widened": True},
            )
        view = booking_slot_view(booking, session.tz)
        intro = _copy(lang, "confirm_cancel")
        return _say(request, proposal_text(lang, [view], intro=intro), "confirm_cancel")

    def _after_faq(
        self,
        request: CompletionRequest,
        messages: list[dict[str, Any]],
        session: SessionView,
        lang: str,
        output: dict[str, Any],
    ) -> CompletionResponse:
        hits = output.get("hits")
        threshold = float(output.get("threshold", 1.0))
        if not isinstance(hits, list) or not hits or not isinstance(hits[0], dict):
            return _say(request, _copy(lang, "unknown"), "unknown", unknown=True)
        top = hits[0]
        score = float(top.get("score", 0))
        excerpt = str(top.get("excerpt") or "")
        doc_id = str(top.get("doc_id") or "")
        if (
            score < threshold
            or top.get("trust") == "untrusted"
            or has_injection(excerpt)
        ):
            if top.get("trust") == "untrusted" or has_injection(excerpt):
                return _say(request, _copy(lang, "injection"), "unknown", unknown=True)
            return _say(request, _copy(lang, "unknown"), "unknown", unknown=True)
        if lang == "es":
            body = f"{excerpt} Fuente: {doc_id}."
        else:
            body = f"{excerpt} Source: {doc_id}."
        if goal_of(messages) == "schedule" and latest_slots(messages):
            slot = latest_slots(messages)[0]
            body = (
                body
                + "\n"
                + proposal_text(
                    lang, [slot], intro=_copy(lang, "back_to_slot"), confirm_option=1
                )
            )
        return _say(request, body, "faq_answer", citations=[doc_id])

    def _from_user(
        self,
        request: CompletionRequest,
        messages: list[dict[str, Any]],
        session: SessionView,
        lang: str,
    ) -> CompletionResponse:
        text = last_user_text(messages)
        markers = other_markers(session.candidate_id)
        if mentions_other(text, markers):
            return _say(request, _copy(lang, "other"), "refusal")
        if is_handoff(text):
            return _say(request, _copy(lang, "handoff"), "handoff")
        if is_refusal(text):
            return _say(request, _copy(lang, "refused"), "refusal")
        if is_ood(text):
            return _say(request, _copy(lang, "unknown"), "unknown", unknown=True)
        if (has_injection(text) and not is_concrete_booking(text)) or is_faq(text):
            return self._tools(request, [self._call("search_faq", {"query": text})])
        joined = "\n".join(user_texts(messages))
        if is_ambiguous_tuesday(text) and not has_concrete_date(joined):
            first, second = next_tuesdays(session.now)
            return _say(request, _ask_tuesday(lang, first, second), "clarify")
        goal = goal_of(messages)
        if goal == "cancel" or is_cancel_action(text):
            if own_booking(messages) is None and not _lookup_done(messages):
                return self._tools(
                    request,
                    [self._call("get_booking", {"candidate_id": session.candidate_id})],
                )
            if is_yes(text):
                booking = own_booking(messages)
                if booking is None:
                    return _say(request, _copy(lang, "no_booking"), "clarify")
                return self._tools(
                    request,
                    [
                        self._call(
                            "cancel_booking",
                            {
                                "booking_id": booking["id"],
                                "candidate_id": session.candidate_id,
                            },
                        )
                    ],
                )
            return self._after_lookup(request, messages, session, lang)
        if goal == "reschedule" or is_reschedule_action(text):
            if not _lookup_done(messages):
                return self._tools(
                    request,
                    [self._call("get_booking", {"candidate_id": session.candidate_id})],
                )
            if is_yes(text):
                slot = select_slot(messages, text)
                if slot is None:
                    return _say(request, _copy(lang, "not_that"), "clarify")
                return self._hold(request, session, slot)
            if option_index(text) is not None:
                return self._restate(
                    request, messages, lang, text, "confirm_reschedule"
                )
            if not latest_slots(messages):
                return self._list(request, messages, session, widened=True)
            return self._after_list(
                request,
                messages,
                session,
                lang,
                {"slots": latest_slots(messages), "widened": True},
            )
        if goal == "schedule" or is_schedule_action(text):
            if find_in_users(messages, extract_interviewer) is None:
                return _say(request, _copy(lang, "who"), "clarify")
            if is_yes(text):
                if extract_clock(text) and select_slot(messages, text) is None:
                    return _say(request, _copy(lang, "not_that"), "clarify")
                slot = select_slot(messages, text)
                if slot is None:
                    return _say(request, _copy(lang, "need_yes"), "confirm_request")
                return self._hold(request, session, slot)
            if option_index(text) is not None and latest_slots(messages):
                return self._restate(request, messages, lang, text, "confirm_request")
            if not latest_slots(messages):
                widened = extract_date(joined) is None
                return self._list(request, messages, session, widened=widened)
            return self._after_list(
                request,
                messages,
                session,
                lang,
                {"slots": latest_slots(messages), "widened": True},
            )
        return _say(request, _copy(lang, "unknown"), "unknown", unknown=True)

    def _hold(
        self,
        request: CompletionRequest,
        session: SessionView,
        slot: dict[str, Any],
    ) -> CompletionResponse:
        return self._tools(
            request,
            [
                self._call(
                    "hold_slot",
                    {
                        "interviewer_id": slot["interviewer_id"],
                        "candidate_id": session.candidate_id,
                        "start": slot["start"],
                        "end": slot["end"],
                    },
                )
            ],
        )

    def _list(
        self,
        request: CompletionRequest,
        messages: list[dict[str, Any]],
        session: SessionView,
        *,
        widened: bool,
    ) -> CompletionResponse:
        interviewer = find_in_users(messages, extract_interviewer) or "iv-ana"
        zone = find_in_users(messages, extract_zone) or session.tz
        date_text = None if widened else find_in_users(messages, extract_date)
        start, end = list_window(
            zone, session.now, date_text, widened or date_text is None
        )
        return self._tools(
            request,
            [
                self._call(
                    "list_availability",
                    {
                        "interviewer_id": interviewer,
                        "range_start": start,
                        "range_end": end,
                        "candidate_tz": zone,
                        "duration_minutes": 45,
                        "limit": 3,
                    },
                )
            ],
        )

    def _restate(
        self,
        request: CompletionRequest,
        messages: list[dict[str, Any]],
        lang: str,
        text: str,
        purpose: str,
    ) -> CompletionResponse:
        slots = latest_slots(messages)
        index = option_index(text) or 1
        if index < 1 or index > len(slots):
            return _say(request, _copy(lang, "not_that"), "clarify")
        chosen = slots[index - 1]
        intro = _copy(lang, "restate")
        line = format_slot_line(1, chosen, lang)
        if lang == "es":
            ask = "Respondé sí para confirmar la opción 1."
        else:
            ask = "Reply yes to confirm option 1."
        return _say(request, f"{intro}\n{line}\n{ask}", purpose)


def _lookup_done(messages: list[dict[str, Any]]) -> bool:
    return any(
        payload.get("name") == "get_booking" and payload.get("status") == "OK"
        for payload in tool_payloads(messages)
    )


def _cancelled(messages: list[dict[str, Any]], booking_id: str) -> bool:
    for payload in tool_payloads(messages):
        if payload.get("name") == "cancel_booking" and payload.get("status") == "OK":
            output = payload.get("output")
            if isinstance(output, dict) and output.get("booking_id") == booking_id:
                return True
    return False


def _last_output(messages: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    found: dict[str, Any] | None = None
    for payload in tool_payloads(messages):
        if payload.get("name") == name and payload.get("status") == "OK":
            output = payload.get("output")
            if isinstance(output, dict):
                found = output
    return found


def _intro_miss(lang: str, clock: str, zone: str) -> str:
    label = zone_phrase(zone)
    if lang == "es":
        return (
            f"El horario {clock} ({label}) no está libre. "
            "Puedo ofrecerte estas opciones."
        )
    return f"The time {clock} ({label}) is not free. I can offer these options."


def _ask_tuesday(lang: str, first: str, second: str) -> str:
    if lang == "es":
        return (
            f"¿Te referís al martes {first} o al martes {second}? "
            "Respondé con la fecha. Todavía no reservé nada."
        )
    return (
        f"Do you mean Tuesday {first} or Tuesday {second}? "
        "Reply with the date. I have not booked anything."
    )


def _copy(lang: str, key: str) -> str:
    table: dict[str, tuple[str, str]] = {
        "offer": (
            "Puedo ofrecerte estas opciones.",
            "I can offer these options.",
        ),
        "reschedule_offer": (
            "Para mover tu entrevista puedo ofrecerte estas opciones.",
            "To move your interview I can offer these options.",
        ),
        "pending": (
            "La entrevista quedó reservada en el calendario interno. "
            "Un recruiter tiene que aprobar el correo antes de que salga. "
            "Todavía no se envió. Cuando lo aprueben, te llega a tu casilla. "
            "Si preferís una persona del equipo, lo pedís y listo.",
            "The interview is on the internal calendar. A recruiter has to approve "
            "the email before it goes out. Nothing was sent yet. After approval it "
            "reaches your inbox. You can ask for a person on the team at any time.",
        ),
        "done": (
            "Listo. El correo quedó en la bandeja de salida después de la aprobación. "
            "Si querés cambiar o cancelar, lo decís.",
            "Done. The email is in the outbox after approval. "
            "If you want to change or cancel, say so.",
        ),
        "cancelled_done": (
            "Listo. La entrevista quedó cancelada y el aviso "
            "ya está en la bandeja de salida.",
            "Done. The interview is cancelled and the notice is in the outbox.",
        ),
        "rejected": (
            "El recruiter no aprobó el correo. No se envió nada "
            "y no voy a reintentar ese envío. "
            "Una persona del equipo te escribe para el siguiente paso.",
            "The recruiter did not approve the email. Nothing was sent "
            "and I will not retry "
            "that send. A person on the team will write with the next step.",
        ),
        "refused": (
            "No reservé nada. Si más adelante querés un horario, escribime. "
            "También podés pedir una persona del equipo.",
            "I did not book anything. If you want a time later, write again. "
            "You can also ask for a person on the team.",
        ),
        "handoff": (
            "Te paso con una persona del equipo de Taller Aurora. "
            "No hice ninguna acción externa.",
            "I am handing this to a person on the Taller Aurora team. "
            "I took no external action.",
        ),
        "unknown": (
            "No tengo esa información. Puedo pasarte con una persona del equipo.",
            "I don't know that. I can hand you to a person on the team.",
        ),
        "other": (
            "Solo puedo hablar de tu propia entrevista. "
            "No comparto datos de otras personas.",
            "I can only talk about your own interview. "
            "I do not share anyone else's data.",
        ),
        "kill": (
            "La entrevista quedó reservada en el calendario interno. "
            "Los correos externos están apagados, así que "
            "no salió ninguna invitación.",
            "The interview is on the internal calendar. "
            "External email is switched off, "
            "so no invitation went out.",
        ),
        "expired": (
            "La aprobación venció. No envié el correo. "
            "Si hace falta, una persona del equipo lo retoma.",
            "The approval expired. I did not send the email. "
            "A person on the team can pick it up.",
        ),
        "expired_hold": (
            "La reserva temporal venció. No quedó tomada.",
            "The temporary hold expired. Nothing was booked.",
        ),
        "taken": (
            "Ese horario se ocupó mientras lo confirmabas. No hice una reserva doble.",
            "That time was taken while you were confirming. I did not double-book it.",
        ),
        "none": (
            "No tengo horarios libres en esa ventana. "
            "Te puedo pasar con una persona del equipo.",
            "I have no free times in that window. "
            "I can hand you to a person on the team.",
        ),
        "need_yes": (
            "Para reservar necesito un sí explícito sobre una de las opciones. "
            "Todavía no reservé.",
            "To book I need an explicit yes on one of the options. "
            "I have not booked yet.",
        ),
        "not_that": (
            "Ese horario no está entre las opciones que te mostré. No reservé nada.",
            "That time is not one of the options I showed. I did not book anything.",
        ),
        "who": (
            "¿Con quién querés entrevistarte: Ana Luz, Bruno Paz, "
            "Camila Norte o Elena Sur?",
            "Who do you want to meet: Ana Luz, Bruno Paz, Camila Norte or Elena Sur?",
        ),
        "confirm_cancel": (
            "Esta es tu entrevista. Respondé sí para confirmar la cancelación. "
            "Todavía no la cancelé.",
            "This is your interview. Reply yes to confirm the cancellation. "
            "I have not cancelled it.",
        ),
        "no_booking": (
            "No tengo una entrevista activa a tu nombre. No cancelé nada.",
            "I do not have an active interview under your name. "
            "I did not cancel anything.",
        ),
        "injection": (
            "Ese texto pide saltear las reglas. No lo voy a hacer "
            "y no voy a mandar correos por eso.",
            "That text asks me to skip the rules. I will not do that "
            "and I will not send email because of it.",
        ),
        "restate": (
            "Dejo solo esta opción.",
            "I will keep only this option.",
        ),
        "back_to_slot": (
            "Cuando quieras seguimos con la entrevista.",
            "Whenever you want, we can continue with the interview.",
        ),
    }
    spanish, english = table[key]
    return spanish if lang == "es" else english
