"""Shared phrasing and reading of the scripted conversation.

The provider and the confirmation gate both use these helpers, so the slot a
person confirms is the slot that can be booked.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from scheduling_agent.retrieval import fold
from scheduling_agent.roster import INTERVIEWERS
from scheduling_agent.timeutil import (
    MONTHS_ES,
    WEEKDAYS_EN,
    WEEKDAYS_ES,
    combine_local,
    parse_iso,
    to_canonical,
)

_LINE = re.compile(
    r"^(\d+)\)\s+\S+\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})-(\d{2}:\d{2})\s+(\S+)"
)
_SLOT_LINE = re.compile(
    r"^(\d+)\)\s+\S+\s+(\d{2})/(\d{2})\s+(\d{2}:\d{2})\s+\(([^)]+)\)"
)
_SHORT_ACCEPT = re.compile(
    r"^(?:(?:la|el|opcion|option)\s+([123])"
    r"|(?:ese|esa|ese horario|that one|that slot))\.?$"
)
_SHORT_ES = {
    "lunes": "lun",
    "martes": "mar",
    "miércoles": "mie",
    "miercoles": "mie",
    "jueves": "jue",
    "viernes": "vie",
    "sábado": "sab",
    "sabado": "sab",
    "domingo": "dom",
}
_SHORT_EN = {
    "Monday": "Mon",
    "Tuesday": "Tue",
    "Wednesday": "Wed",
    "Thursday": "Thu",
    "Friday": "Fri",
    "Saturday": "Sat",
    "Sunday": "Sun",
}
_ZONE = re.compile(r"(?:America|Europe)(?:/[A-Za-z0-9_+-]+)+|\bUTC\b")
_CLOCK = re.compile(r"\b(\d{1,2}:\d{2})\b")
_YES = re.compile(r"\b(si|yes|confirmo|confirm|dale)\b")
_OPTION = re.compile(r"\b(?:opcion|option)\s+(\d)\b")
_CONFIRM_OPT = re.compile(r"confirmar la opcion (\d)|confirm option (\d)")
_INJECTION = (
    "ignore the rules",
    "ignore previous",
    "email all candidates",
    "ignora las reglas",
    "envia el correo a todos",
)
_FAQ = (
    "reprogram",
    "reschedul",
    "politic",
    "policy",
    "accesib",
    "privacy",
    "privacid",
    "zona horaria",
    "time zone",
    "prepar",
    "camara",
    "camera",
    "llegar tarde",
    "running late",
    "feedback",
    "devoluc",
    "remoto",
    "remote tool",
    "subtitul",
    "caption",
    "duracion",
    "duration",
    "quien entrevista",
    "who interviews",
)
_OOD = (
    "clima",
    "weather",
    "receta",
    "recipe",
    "acciones",
    "stock price",
)
_HANDOFF = (
    "persona del equipo",
    "persona real",
    "hablar con una persona",
    "human please",
    "talk to a person",
    "pasame con",
)


@dataclass(frozen=True)
class SessionView:
    candidate_id: str
    name: str
    tz: str
    email: str
    now: datetime
    lang: str


def loads_obj(text: str) -> dict[str, Any]:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("expected object")
    return value


def parse_session(messages: list[dict[str, Any]]) -> SessionView:
    for message in messages:
        content = str(message.get("content") or "")
        if "[session]" not in content:
            continue
        fields: dict[str, str] = {}
        for token in content.split("[session]", 1)[1].split():
            if "=" in token:
                key, value = token.split("=", 1)
                fields[key] = value
        return SessionView(
            candidate_id=fields["candidate_id"],
            name=fields.get("name", ""),
            tz=fields["tz"],
            email=fields["email"],
            now=parse_iso(fields["now"]),
            lang=fields.get("lang", "es"),
        )
    raise ValueError("session header missing")


def user_texts(messages: list[dict[str, Any]]) -> list[str]:
    return [
        str(message.get("content") or "")
        for message in messages
        if message.get("role") == "user"
    ]


def last_user_text(messages: list[dict[str, Any]]) -> str:
    texts = user_texts(messages)
    return texts[-1] if texts else ""


def boundary_index(messages: list[dict[str, Any]]) -> int:
    """Last user turn or recruiter decision.

    Tool results after this index belong to the current step.
    """
    index = 0
    for position, message in enumerate(messages):
        if message.get("role") == "user":
            index = position
        content = str(message.get("content") or "")
        if message.get("role") == "system" and content.startswith(
            "recruiter_decision="
        ):
            index = position
    return index


def tool_payloads(
    messages: list[dict[str, Any]], *, after: int = -1
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for position, message in enumerate(messages):
        if position <= after or message.get("role") != "tool":
            continue
        found.append(loads_obj(str(message["content"])))
    return found


def recruiter_decision(messages: list[dict[str, Any]]) -> dict[str, str] | None:
    index = boundary_index(messages)
    content = str(messages[index].get("content") or "") if messages else ""
    if not content.startswith("recruiter_decision="):
        return None
    fields: dict[str, str] = {}
    for token in content.split():
        if "=" in token:
            key, value = token.split("=", 1)
            fields[key] = value
    return fields


def detect_lang(text: str, default: str) -> str:
    folded = fold(text)
    spanish = sum(
        token in folded
        for token in (
            "hola",
            "quiero",
            "entrevista",
            "opcion",
            "necesito",
            "confirmo",
            "martes",
            "zona",
            "reprogram",
            "cancela",
        )
    )
    english = sum(
        token in folded
        for token in (
            "hello",
            "i want",
            "interview",
            "option",
            "please",
            "tuesday",
            "schedule",
            "reschedule",
            "yes",
        )
    )
    if english > spanish:
        return "en"
    if spanish > english:
        return "es"
    return default


def has_injection(text: str) -> bool:
    folded = fold(text)
    return any(marker in folded for marker in _INJECTION)


def is_refusal(text: str) -> bool:
    folded = fold(text).strip()
    if "no problem" in folded or "no hay" in folded:
        return False
    if re.match(r"^no\b", folded):
        return True
    return any(
        phrase in folded
        for phrase in (
            "no gracias",
            "mejor no",
            "no confirmo",
            "i refuse",
            "do not book",
        )
    )


def is_yes(text: str) -> bool:
    if is_refusal(text):
        return False
    return _YES.search(fold(text)) is not None


def is_ambiguous_tuesday(text: str) -> bool:
    folded = fold(text)
    if "martes que viene" not in folded and "next tuesday" not in folded:
        return False
    if re.search(r"\d{4}-\d{2}-\d{2}", text):
        return False
    if re.search(r"\b\d{1,2}\s+de\s+(abril|mayo)\b", folded):
        return False
    return True


def has_concrete_date(text: str) -> bool:
    if re.search(r"\d{4}-\d{2}-\d{2}", text):
        return True
    folded = fold(text)
    if re.search(r"\b\d{1,2}\s+de\s+[a-z]+\s+de\s+\d{4}\b", folded):
        return True
    return re.search(r"\b(?:april|may)\s+\d{1,2},?\s+\d{4}\b", folded) is not None


def is_concrete_booking(text: str) -> bool:
    folded = fold(text)
    if not has_concrete_date(text):
        return False
    return "entrevista" in folded or "interview" in folded


def is_schedule_action(text: str) -> bool:
    if is_ambiguous_tuesday(text):
        return True
    folded = fold(text)
    phrases = (
        "quiero una entrevista",
        "quiero entrevist",
        "agendar",
        "i want an interview",
        "schedule an interview",
        "book an interview",
    )
    if any(phrase in folded for phrase in phrases):
        return True
    return has_concrete_date(text) and ("entrevista" in folded or "interview" in folded)


def is_cancel_action(text: str) -> bool:
    folded = fold(text)
    if (
        "como cancel" in folded
        or "how do i cancel" in folded
        or "how to cancel" in folded
    ):
        return False
    phrases = (
        "cancela mi",
        "cancela la entrevista",
        "cancel my interview",
        "cancel the interview",
    )
    return any(phrase in folded for phrase in phrases)


def is_reschedule_action(text: str) -> bool:
    folded = fold(text)
    if "?" in text and not has_concrete_date(text):
        return False
    phrases = (
        "reprograma mi",
        "reprogramar mi",
        "reprograma la entrevista",
        "reschedule my",
        "move my interview",
        "cambiar mi entrevista",
    )
    return any(phrase in folded for phrase in phrases)


def is_faq(text: str) -> bool:
    if (
        is_concrete_booking(text)
        or is_cancel_action(text)
        or is_reschedule_action(text)
    ):
        return False
    folded = fold(text)
    return any(hint in folded for hint in _FAQ) or (has_injection(text) and "?" in text)


def is_ood(text: str) -> bool:
    folded = fold(text)
    return any(hint in folded for hint in _OOD)


def is_handoff(text: str) -> bool:
    folded = fold(text)
    return any(hint in folded for hint in _HANDOFF)


def mentions_other(text: str, markers: tuple[str, ...]) -> bool:
    folded = fold(text)
    return any(fold(marker) in folded for marker in markers)


def extract_interviewer(text: str) -> str | None:
    folded = fold(text)
    for interviewer_id, row in INTERVIEWERS.items():
        if fold(row["name"]) in folded or interviewer_id in folded:
            return interviewer_id
    return None


def extract_zone(text: str) -> str | None:
    match = _ZONE.search(text)
    if match is None:
        return None
    return match.group(0)


def extract_clock(text: str) -> str | None:
    match = _CLOCK.search(text)
    if match is None:
        return None
    hours, minutes = match.group(1).split(":")
    return f"{int(hours):02d}:{minutes}"


def extract_date(text: str) -> str | None:
    iso = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if iso:
        return iso.group(1)
    folded = fold(text)
    spanish = re.search(r"\b(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(\d{4})\b", folded)
    if spanish:
        month = MONTHS_ES.get(spanish.group(2))
        if month is not None:
            return (
                f"{int(spanish.group(3)):04d}-{month:02d}-{int(spanish.group(1)):02d}"
            )
    english = re.search(r"\b(april|may)\s+(\d{1,2}),?\s+(\d{4})\b", folded)
    if english:
        month = {"april": 4, "may": 5}[english.group(1)]
        return f"{int(english.group(3)):04d}-{month:02d}-{int(english.group(2)):02d}"
    return None


def find_in_users(messages: list[dict[str, Any]], fn: Any) -> Any:
    for text in reversed(user_texts(messages)):
        found = fn(text)
        if found:
            return found
    return None


def option_index(text: str) -> int | None:
    match = _OPTION.search(fold(text))
    if match is None:
        return None
    return int(match.group(1))


def short_accept_index(text: str) -> int | None:
    """1-based option, or 0 when a bare yes accepts the pending slot.

    ``None`` means this turn is not a short confirmation. A longer sentence
    such as "mejor la opción 2" stays on the restate path.
    """
    if is_refusal(text):
        return None
    match = _SHORT_ACCEPT.match(fold(text).strip())
    if match is not None:
        raw = match.group(1)
        return int(raw) if raw else 0
    if is_yes(text):
        return 0
    return None


def confirm_index(text: str) -> int | None:
    match = _CONFIRM_OPT.search(fold(text))
    if match is None:
        return None
    raw = match.group(1) or match.group(2)
    return int(raw)


def last_assistant_text(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "assistant" and not message.get("tool_calls"):
            return str(message.get("content") or "")
    return ""


def parse_option_lines(text: str) -> list[tuple[int, str, str, str]]:
    """Return `(index, date, start, zone_or_phrase)` per slot line.

    The date field is `YYYY-MM-DD` for the old line and `DD/MM` for
    `1) mar 14/04 15:00 (ART, UTC-3)`.
    """
    found: list[tuple[int, str, str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        current = _SLOT_LINE.match(stripped)
        if current:
            found.append(
                (
                    int(current.group(1)),
                    f"{current.group(2)}/{current.group(3)}",
                    current.group(4),
                    current.group(5),
                )
            )
            continue
        older = _LINE.match(stripped)
        if older:
            found.append(
                (int(older.group(1)), older.group(2), older.group(3), older.group(5))
            )
    return found


def latest_slots(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for payload in tool_payloads(messages):
        if payload.get("name") == "list_availability" and payload.get("status") == "OK":
            output = payload.get("output", {})
            if isinstance(output, dict) and isinstance(output.get("slots"), list):
                slots = [item for item in output["slots"] if isinstance(item, dict)]
    return slots


def zone_phrase(tz: str) -> str:
    """One display form: short name and a numeric offset.

    Buenos Aires is UTC-3 all year. UTC slots use `UTC, UTC+0`.
    """
    if tz == "America/Argentina/Buenos_Aires":
        return "ART, UTC-3"
    if tz == "UTC":
        return "UTC, UTC+0"
    return tz


def match_slot(
    slots: list[dict[str, Any]], date_text: str, start: str, zone: str
) -> dict[str, Any] | None:
    for slot in slots:
        local_date = str(slot.get("local_date") or "")
        phrase = zone_phrase(str(slot.get("interviewer_tz") or ""))
        day_month = ""
        if len(local_date) == 10:
            day_month = f"{local_date[8:10]}/{local_date[5:7]}"
        date_ok = local_date == date_text or day_month == date_text
        zone_ok = slot.get("interviewer_tz") == zone or phrase == zone
        if date_ok and slot.get("local_start") == start and zone_ok:
            return slot
    return None


def select_slot(
    messages: list[dict[str, Any]], user_text: str
) -> dict[str, Any] | None:
    slots = latest_slots(messages)
    assistant = last_assistant_text(messages)
    options = parse_option_lines(assistant)
    if not slots or not options:
        return None
    wanted = option_index(user_text) or confirm_index(assistant) or options[0][0]
    chosen = next((row for row in options if row[0] == wanted), None)
    if chosen is None:
        return None
    slot = match_slot(slots, chosen[1], chosen[2], chosen[3])
    if slot is None:
        return None
    clock = extract_clock(user_text)
    if clock is not None and clock not in {
        str(slot.get("local_start")),
        str(slot.get("candidate_start")),
    }:
        return None
    return slot


def format_slot_line(index: int, slot: dict[str, Any], lang: str) -> str:
    """Numbered slot. The clock always carries a zone and an offset."""
    names = _SHORT_ES if lang == "es" else _SHORT_EN
    weekday_key = str(slot["weekday_es"] if lang == "es" else slot["weekday_en"])
    weekday = names.get(weekday_key, weekday_key[:3])
    local_date = str(slot["local_date"])
    day_month = f"{local_date[8:10]}/{local_date[5:7]}"
    phrase = zone_phrase(str(slot["interviewer_tz"]))
    line = f"{index}) {weekday} {day_month} {slot['local_start']} ({phrase})"
    line += f" | {slot['interviewer_name']} | {slot['duration_minutes']} min"
    if slot.get("candidate_tz") != slot.get("interviewer_tz"):
        other = zone_phrase(str(slot["candidate_tz"]))
        if lang == "es":
            line += f" | candidato {slot['candidate_start']} ({other})"
        else:
            line += f" | candidate {slot['candidate_start']} ({other})"
    return line


def render_pending_slot(slot: dict[str, Any] | None, index: int = 1) -> str:
    """One context line. `pending_slot: none` when nothing is waiting."""
    if slot is None:
        return "pending_slot: none"
    label = format_slot_line(index, slot, "es").split(" | ", 1)[0]
    return (
        "pending_slot: "
        f"interviewer_id={slot['interviewer_id']} "
        f"start={slot['start']} end={slot['end']} label={label}"
    )


def proposal_text(
    lang: str,
    slots: list[dict[str, Any]],
    *,
    intro: str,
    confirm_option: int = 1,
) -> str:
    lines = [
        format_slot_line(index, slot, lang) for index, slot in enumerate(slots, start=1)
    ]
    if lang == "es":
        ask = f"Respondé sí para confirmar la opción {confirm_option}."
    else:
        ask = f"Reply yes to confirm option {confirm_option}."
    return "\n".join([intro, *lines, ask])


def next_tuesdays(now: datetime) -> tuple[str, str]:
    local = now.astimezone(ZoneInfo("America/Argentina/Buenos_Aires")).date()
    ahead = (1 - local.weekday()) % 7
    if ahead == 0:
        ahead = 7
    first = local + timedelta(days=ahead)
    second = first + timedelta(days=7)
    return first.isoformat(), second.isoformat()


def list_window(
    tz_name: str, now: datetime, date_text: str | None, widened: bool
) -> tuple[str, str]:
    if date_text and not widened:
        start = combine_local(date_text, "00:00", tz_name)
        end = start + timedelta(days=1)
    else:
        start = now.astimezone(ZoneInfo(tz_name))
        end = start + timedelta(days=7)
    return to_canonical(start), to_canonical(end)


def previous_call_args(
    messages: list[dict[str, Any]], tool_name: str
) -> dict[str, Any] | None:
    for message in reversed(messages):
        calls = message.get("tool_calls")
        if message.get("role") != "assistant" or not isinstance(calls, list):
            continue
        for call in reversed(calls):
            if isinstance(call, dict) and call.get("name") == tool_name:
                arguments = call.get("arguments", {})
                if isinstance(arguments, dict):
                    return arguments
    return None


def goal_of(messages: list[dict[str, Any]]) -> str:
    texts = user_texts(messages)
    if any(is_cancel_action(text) for text in texts) and not any(
        is_reschedule_action(text) for text in texts
    ):
        return "cancel"
    if any(is_reschedule_action(text) for text in texts):
        return "reschedule"
    if any(is_schedule_action(text) for text in texts):
        return "schedule"
    return "none"


def own_booking(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    found: dict[str, Any] | None = None
    for payload in tool_payloads(messages):
        if payload.get("name") == "get_booking" and payload.get("status") == "OK":
            output = payload.get("output", {})
            if isinstance(output, dict):
                rows = output.get("bookings", [])
                if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                    found = rows[0]
                elif isinstance(rows, list):
                    found = None
    return found


def booking_slot_view(booking: dict[str, Any], candidate_tz: str) -> dict[str, Any]:
    interviewer_id = str(booking["interviewer_id"])
    roster = INTERVIEWERS[interviewer_id]
    start = parse_iso(str(booking["start"]))
    end = parse_iso(str(booking["end"]))
    zone = ZoneInfo(roster["timezone"])
    local = start.astimezone(zone)
    local_end = end.astimezone(zone)
    cand = start.astimezone(ZoneInfo(candidate_tz))
    cand_end = end.astimezone(ZoneInfo(candidate_tz))
    return {
        "interviewer_id": interviewer_id,
        "interviewer_name": roster["name"],
        "start": to_canonical(start),
        "end": to_canonical(end),
        "duration_minutes": int((end - start).total_seconds() // 60),
        "local_date": local.strftime("%Y-%m-%d"),
        "local_start": local.strftime("%H:%M"),
        "local_end": local_end.strftime("%H:%M"),
        "interviewer_tz": roster["timezone"],
        "candidate_tz": candidate_tz,
        "candidate_start": cand.strftime("%H:%M"),
        "candidate_end": cand_end.strftime("%H:%M"),
        "weekday_es": WEEKDAYS_ES[local.weekday()],
        "weekday_en": WEEKDAYS_EN[local.weekday()],
    }
