"""Tool registry. Every tool has an effect class, a schema and a budget."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

from scheduling_agent.approvals import param_hash, slot_hash
from scheduling_agent.calendar import CalendarError
from scheduling_agent.logging_setup import configure_logging, log_event
from scheduling_agent.roster import INTERVIEWERS
from scheduling_agent.runtime import OutboxMessage, RunContext
from scheduling_agent.timeutil import (
    WEEKDAYS_EN,
    parse_iso,
    to_canonical,
)

Effect = str

READ = "read"
INTERNAL = "internal_reversible"
EXTERNAL = "external"
EFFECT_RANK = {READ: 0, INTERNAL: 1, EXTERNAL: 2}

# Naive values are rejected on purpose. Do not guess UTC or Buenos Aires.
NAIVE_DATETIME_FIX = (
    "A datetime must include an offset, for example 2026-10-20T10:00:00-03:00. "
    "Naive datetimes are rejected; they are not read as UTC or as Buenos Aires."
)

_OBJECT = "object"
_STRING = "string"
_INT = "integer"


def _schema(
    required: list[str],
    properties: dict[str, dict[str, object]],
) -> dict[str, object]:
    return {
        "type": _OBJECT,
        "additionalProperties": False,
        "required": required,
        "properties": properties,
    }


def _str() -> dict[str, object]:
    return {"type": _STRING}


def _int(minimum: int, maximum: int) -> dict[str, object]:
    return {"type": _INT, "minimum": minimum, "maximum": maximum}


TOOL_SPECS: dict[str, dict[str, object]] = {
    "list_availability": {
        "effect_class": READ,
        "description": "List up to 3 free interview slots in the mock calendar.",
        "parameters": _schema(
            ["interviewer_id", "range_start", "range_end", "candidate_tz"],
            {
                "interviewer_id": _str(),
                "range_start": _str(),
                "range_end": _str(),
                "candidate_tz": _str(),
                "duration_minutes": _int(15, 180),
                "limit": _int(1, 3),
            },
        ),
    },
    "search_faq": {
        "effect_class": READ,
        "description": "Search the synthetic FAQ. Returns document ids and excerpts.",
        "parameters": _schema(["query"], {"query": _str()}),
    },
    "get_booking": {
        "effect_class": READ,
        "description": "Read the session candidate's bookings.",
        "parameters": _schema(["candidate_id"], {"candidate_id": _str()}),
    },
    "hold_slot": {
        "effect_class": INTERNAL,
        "description": "Place a temporary hold on a free slot.",
        "parameters": _schema(
            ["interviewer_id", "candidate_id", "start", "end"],
            {
                "interviewer_id": _str(),
                "candidate_id": _str(),
                "start": _str(),
                "end": _str(),
            },
        ),
    },
    "release_hold": {
        "effect_class": INTERNAL,
        "description": "Release a hold.",
        "parameters": _schema(
            ["hold_id", "candidate_id"], {"hold_id": _str(), "candidate_id": _str()}
        ),
    },
    "book_slot": {
        "effect_class": INTERNAL,
        "description": (
            "Convert a hold into a booking. "
            "Requires user confirmation of the same slot."
        ),
        "parameters": _schema(
            ["hold_id", "candidate_id", "interviewer_id", "start", "end"],
            {
                "hold_id": _str(),
                "candidate_id": _str(),
                "interviewer_id": _str(),
                "start": _str(),
                "end": _str(),
            },
        ),
    },
    "cancel_booking": {
        "effect_class": INTERNAL,
        "description": "Cancel the session candidate's booking. Requires confirmation.",
        "parameters": _schema(
            ["booking_id", "candidate_id"],
            {"booking_id": _str(), "candidate_id": _str()},
        ),
    },
    "send_invite_email": {
        "effect_class": EXTERNAL,
        "description": "Queue an invite in the outbox. Requires recruiter approval.",
        "parameters": _schema(
            ["booking_id", "candidate_id", "to", "interviewer_id", "start", "timezone"],
            {
                "booking_id": _str(),
                "candidate_id": _str(),
                "to": _str(),
                "interviewer_id": _str(),
                "start": _str(),
                "timezone": _str(),
            },
        ),
    },
    "send_reschedule_email": {
        "effect_class": EXTERNAL,
        "description": "Queue a reschedule notice. Requires recruiter approval.",
        "parameters": _schema(
            ["booking_id", "candidate_id", "to", "interviewer_id", "start", "timezone"],
            {
                "booking_id": _str(),
                "candidate_id": _str(),
                "to": _str(),
                "interviewer_id": _str(),
                "start": _str(),
                "timezone": _str(),
            },
        ),
    },
    "send_cancellation_notice": {
        "effect_class": EXTERNAL,
        "description": "Queue a cancellation notice. Requires recruiter approval.",
        "parameters": _schema(
            ["booking_id", "candidate_id", "to", "interviewer_id", "start", "timezone"],
            {
                "booking_id": _str(),
                "candidate_id": _str(),
                "to": _str(),
                "interviewer_id": _str(),
                "start": _str(),
                "timezone": _str(),
            },
        ),
    },
}


def openai_tools() -> list[dict[str, object]]:
    exported: list[dict[str, object]] = []
    for name, spec in TOOL_SPECS.items():
        exported.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": spec["description"],
                    "parameters": spec["parameters"],
                },
            }
        )
    return exported


def validate_args(name: str, args: dict[str, Any]) -> str | None:
    spec = TOOL_SPECS[name]
    schema = spec["parameters"]
    if not isinstance(schema, dict):
        return "invalid schema"
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        return "invalid schema"
    if schema.get("additionalProperties") is False:
        extra = sorted(set(args) - set(properties))
        if extra:
            return f"unknown fields: {extra}"
    for key in required:
        if key not in args:
            return f"missing {key}"
    for key, raw_spec in properties.items():
        if key not in args or not isinstance(raw_spec, dict):
            continue
        value = args[key]
        expected = raw_spec.get("type")
        if expected == _STRING and not isinstance(value, str):
            return f"{key} must be a string"
        if expected == _INT and (isinstance(value, bool) or not isinstance(value, int)):
            return f"{key} must be an integer"
        if expected == _INT and isinstance(value, int):
            minimum = raw_spec.get("minimum")
            maximum = raw_spec.get("maximum")
            if isinstance(minimum, int) and value < minimum:
                return f"{key} below minimum"
            if isinstance(maximum, int) and value > maximum:
                return f"{key} above maximum"
    return None


def how_to_fix(status: str, detail: str) -> str:
    """Tell the caller what to change. The text is safe to show to a model."""
    folded = detail.lower()
    if "naive datetime" in folded or "invalid iso" in folded:
        return NAIVE_DATETIME_FIX
    if status == "NOT_FOUND" and "interviewer" in folded:
        roster = ", ".join(
            f"{item_id} ({row['name']})" for item_id, row in INTERVIEWERS.items()
        )
        return (
            "Use an exact interviewer id from the roster: "
            f"{roster}. A display name or a slug such as ana-luz is not an id."
        )
    if status == "TOOL_ERROR" and "json" in folded:
        return "Arguments must be one JSON object. " + NAIVE_DATETIME_FIX
    return (
        "Correct the arguments and call the tool again. "
        "Do not repeat the same invalid call. " + NAIVE_DATETIME_FIX
    )


def _failure(
    ctx: RunContext,
    *,
    name: str,
    effect_class: str,
    args: dict[str, Any],
    origin: str,
    status: str,
    detail: str,
    error: str,
) -> dict[str, Any]:
    """A tool problem the model can read. It is not an uncaught exception."""
    return _result(
        ctx,
        name=name,
        effect_class=effect_class,
        args=args,
        origin=origin,
        status=status,
        executed=False,
        output={
            "error": error,
            "detail": detail,
            "how_to_fix": how_to_fix(status, detail),
        },
    )


def invalid_arguments_result(
    ctx: RunContext,
    name: str,
    origin: str,
) -> dict[str, Any]:
    """The model sent tool arguments that were not a JSON object."""
    return _failure(
        ctx,
        name=name or "unknown",
        effect_class=READ,
        args={},
        origin=origin,
        status="TOOL_ERROR",
        detail="tool arguments were not valid JSON",
        error="invalid_json",
    )


def _result(
    ctx: RunContext,
    *,
    name: str,
    effect_class: str,
    args: dict[str, Any],
    origin: str,
    status: str,
    executed: bool,
    output: dict[str, Any],
    approval_id: str = "",
) -> dict[str, Any]:
    digest = param_hash(name, args)
    payload = {
        "name": name,
        "effect_class": effect_class,
        "status": status,
        "executed": executed,
        "origin": origin,
        "param_hash": digest,
        "approval_id": approval_id,
        "output": output,
        "args": args,
    }
    ctx.trace.add("tool_result", **payload)
    log_event(
        configure_logging(),
        20,
        "tool_result",
        ctx.run_id,
        tool=name,
        status=status,
        executed=executed,
    )
    return payload


def _slot_view(
    ctx: RunContext, interviewer_id: str, start: str, end: str, candidate_tz: str
) -> dict[str, Any]:
    interviewer = ctx.calendar.interviewer(interviewer_id)
    start_dt = parse_iso(start)
    end_dt = parse_iso(end)
    zone = ZoneInfo(interviewer.timezone)
    local = start_dt.astimezone(zone)
    local_end = end_dt.astimezone(zone)
    cand_zone = ZoneInfo(candidate_tz)
    cand = start_dt.astimezone(cand_zone)
    cand_end = end_dt.astimezone(cand_zone)
    return {
        "interviewer_id": interviewer.id,
        "interviewer_name": interviewer.name,
        "start": to_canonical(start_dt),
        "end": to_canonical(end_dt),
        "duration_minutes": int((end_dt - start_dt).total_seconds() // 60),
        "local_date": local.strftime("%Y-%m-%d"),
        "local_start": local.strftime("%H:%M"),
        "local_end": local_end.strftime("%H:%M"),
        "interviewer_tz": interviewer.timezone,
        "candidate_tz": candidate_tz,
        "candidate_start": cand.strftime("%H:%M"),
        "candidate_end": cand_end.strftime("%H:%M"),
        "weekday_en": WEEKDAYS_EN[local.weekday()],
    }


def _external_gate(ctx: RunContext, name: str, args: dict[str, Any]) -> tuple[str, str]:
    """Return (status, approval_id). status `approved` means the call may run."""
    if not ctx.external_enabled:
        return "KILL_SWITCH", ""
    if ctx.bypass_gates:
        return "approved", "bypass"
    found = ctx.approvals.classify(name, args)
    if found is None:
        row = ctx.approvals.request(
            approval_id=ctx.ids.next("appr"),
            tool=name,
            args=args,
        )
        return "PENDING_APPROVAL", row.id
    if found.status == "approved":
        return "approved", found.id
    if found.status == "rejected":
        return "REJECTED", found.id
    if found.status == "expired":
        return "EXPIRED", found.id
    return "PENDING_APPROVAL", found.id


def _confirmed_slot(ctx: RunContext, args: dict[str, Any]) -> bool:
    digest = slot_hash(
        interviewer_id=str(args["interviewer_id"]),
        candidate_id=str(args["candidate_id"]),
        start=str(args["start"]),
        end=str(args["end"]),
    )
    return any(
        row.get("slot_hash") == digest and row.get("kind") in {"book", "reschedule"}
        for row in ctx.confirmations
    )


def _confirmed_cancel(ctx: RunContext, booking_id: str) -> bool:
    return any(
        row.get("booking_id") == booking_id
        and row.get("kind") in {"cancel", "reschedule"}
        for row in ctx.confirmations
    )


def _queue(
    ctx: RunContext, kind: str, args: dict[str, Any], approval_id: str
) -> OutboxMessage:
    message = OutboxMessage(
        id=ctx.ids.next("out"),
        kind=kind,
        to=str(args["to"]),
        subject=f"{kind} {args['booking_id']}",
        body=(
            f"{kind} for {args['candidate_id']} with {args['interviewer_id']} "
            f"at {args['start']} {args['timezone']}"
        ),
        approval_id=approval_id,
        param_hash=param_hash(kind, args),
        booking_id=str(args["booking_id"]),
    )
    ctx.outbox.append(message)
    return message


def execute_tool(
    ctx: RunContext,
    name: str,
    args: dict[str, Any],
    origin: str = "policy",
) -> dict[str, Any]:
    """Validate, gate and maybe execute one tool call."""
    spec = TOOL_SPECS.get(name)
    if spec is None:
        return _result(
            ctx,
            name=name,
            effect_class=READ,
            args=args,
            origin=origin,
            status="UNKNOWN_TOOL",
            executed=False,
            output={"detail": "unknown tool"},
        )
    effect = str(spec["effect_class"])
    error = validate_args(name, args)
    if error is not None:
        return _result(
            ctx,
            name=name,
            effect_class=effect,
            args=args,
            origin=origin,
            status="VALIDATION_ERROR",
            executed=False,
            output={"detail": error},
        )
    if (
        ctx.tool_calls >= ctx.settings.max_tool_calls
        or ctx.tool_counts.get(name, 0) >= ctx.settings.per_tool_cap
    ):
        return _result(
            ctx,
            name=name,
            effect_class=effect,
            args=args,
            origin=origin,
            status="BUDGET_EXCEEDED",
            executed=False,
            output={"detail": "tool budget exceeded"},
        )
    candidate_id = args.get("candidate_id")
    if isinstance(candidate_id, str) and candidate_id != ctx.candidate_id:
        return _result(
            ctx,
            name=name,
            effect_class=effect,
            args=args,
            origin=origin,
            status="REFUSED",
            executed=False,
            output={"detail": "other candidate"},
        )
    recipient = args.get("to")
    if isinstance(recipient, str) and recipient != ctx.candidate_email:
        return _result(
            ctx,
            name=name,
            effect_class=effect,
            args=args,
            origin=origin,
            status="REFUSED",
            executed=False,
            output={"detail": "recipient is not the session candidate"},
        )
    ctx.tool_calls += 1
    ctx.tool_counts[name] = ctx.tool_counts.get(name, 0) + 1
    try:
        return _dispatch(ctx, name, effect, args, origin)
    except CalendarError as exc:
        return _failure(
            ctx,
            name=name,
            effect_class=effect,
            args=args,
            origin=origin,
            status=exc.code,
            detail=exc.detail,
            error=exc.code.lower(),
        )
    except (ValueError, TypeError, KeyError) as exc:
        detail = str(exc) or exc.__class__.__name__
        error = "naive_datetime" if "naive datetime" in detail.lower() else "tool_error"
        return _failure(
            ctx,
            name=name,
            effect_class=effect,
            args=args,
            origin=origin,
            status="TOOL_ERROR",
            detail=detail,
            error=error,
        )


def _dispatch(
    ctx: RunContext,
    name: str,
    effect: str,
    args: dict[str, Any],
    origin: str,
) -> dict[str, Any]:
    if effect == EXTERNAL:
        status, approval_id = _external_gate(ctx, name, args)
        if status != "approved":
            return _result(
                ctx,
                name=name,
                effect_class=effect,
                args=args,
                origin=origin,
                status=status,
                executed=False,
                output={"approval_id": approval_id, "detail": status.lower()},
                approval_id=approval_id,
            )
        kind = {
            "send_invite_email": "invite",
            "send_reschedule_email": "reschedule",
            "send_cancellation_notice": "cancellation",
        }[name]
        already = next(
            (item for item in ctx.outbox if item.approval_id == approval_id),
            None,
        )
        if already is not None:
            return _result(
                ctx,
                name=name,
                effect_class=effect,
                args=args,
                origin=origin,
                status="OK",
                executed=False,
                output={
                    "outbox_id": already.id,
                    "kind": already.kind,
                    "detail": "already_queued",
                },
                approval_id=approval_id,
            )
        message = _queue(ctx, kind, args, approval_id)
        return _result(
            ctx,
            name=name,
            effect_class=effect,
            args=args,
            origin=origin,
            status="OK",
            executed=True,
            output={"outbox_id": message.id, "kind": kind},
            approval_id=approval_id,
        )
    if name == "book_slot" and not ctx.bypass_gates and not _confirmed_slot(ctx, args):
        return _result(
            ctx,
            name=name,
            effect_class=effect,
            args=args,
            origin=origin,
            status="NEEDS_CONFIRMATION",
            executed=False,
            output={"detail": "user has not confirmed this slot"},
        )
    if (
        name == "cancel_booking"
        and not ctx.bypass_gates
        and not _confirmed_cancel(ctx, str(args["booking_id"]))
    ):
        return _result(
            ctx,
            name=name,
            effect_class=effect,
            args=args,
            origin=origin,
            status="NEEDS_CONFIRMATION",
            executed=False,
            output={"detail": "user has not confirmed this cancellation"},
        )
    output = _run_internal_or_read(ctx, name, args)
    if name == "hold_slot" and ctx.advance_after_hold_seconds and not ctx.advance_fired:
        ctx.clock.advance(float(ctx.advance_after_hold_seconds))
        ctx.calendar.expire_holds()
        ctx.advance_fired = True
    return _result(
        ctx,
        name=name,
        effect_class=effect,
        args=args,
        origin=origin,
        status="OK",
        executed=True,
        output=output,
    )


def _run_internal_or_read(
    ctx: RunContext, name: str, args: dict[str, Any]
) -> dict[str, Any]:
    if name == "list_availability":
        start = parse_iso(str(args["range_start"]))
        end = parse_iso(str(args["range_end"]))
        limit = int(args.get("limit", 3))
        duration = int(args["duration_minutes"]) if "duration_minutes" in args else None
        slots = ctx.calendar.list_slots(
            interviewer_id=str(args["interviewer_id"]),
            range_start=start,
            range_end=end,
            duration_minutes=duration,
            limit=min(limit, 3),
        )
        widened = (end - start) > timedelta(hours=36)
        views = [
            _slot_view(
                ctx,
                slot.interviewer_id,
                slot.canonical_start(),
                slot.canonical_end(),
                str(args["candidate_tz"]),
            )
            for slot in slots
        ]
        return {"slots": views, "widened": widened}
    if name == "search_faq":
        hits = ctx.retriever.search(str(args["query"]), k=ctx.settings.retrieval_k)
        return {
            "threshold": ctx.settings.retrieval_threshold,
            "hits": [
                {
                    "doc_id": hit.doc_id,
                    "title": hit.title,
                    "score": hit.score,
                    "excerpt": hit.excerpt,
                    "trust": hit.trust,
                }
                for hit in hits
            ],
        }
    if name == "get_booking":
        rows = ctx.calendar.bookings_for(ctx.candidate_id)
        return {
            "bookings": [
                {
                    "id": row.id,
                    "interviewer_id": row.interviewer_id,
                    "candidate_id": row.candidate_id,
                    "start": to_canonical(row.start),
                    "end": to_canonical(row.end),
                    "status": row.status,
                }
                for row in rows
            ]
        }
    if name == "hold_slot":
        hold = ctx.calendar.hold(
            hold_id=ctx.ids.next("hold"),
            interviewer_id=str(args["interviewer_id"]),
            candidate_id=str(args["candidate_id"]),
            start=parse_iso(str(args["start"])),
            end=parse_iso(str(args["end"])),
            ttl_seconds=ctx.settings.hold_ttl_seconds,
        )
        return {
            "hold_id": hold.id,
            "interviewer_id": hold.interviewer_id,
            "candidate_id": hold.candidate_id,
            "start": to_canonical(hold.start),
            "end": to_canonical(hold.end),
            "expires_at": to_canonical(hold.expires_at),
        }
    if name == "release_hold":
        hold = ctx.calendar.release(str(args["hold_id"]))
        return {"hold_id": hold.id, "status": "released"}
    if name == "book_slot":
        booking = ctx.calendar.book(
            booking_id=ctx.ids.next("book"),
            hold_id=str(args["hold_id"]),
            candidate_id=str(args["candidate_id"]),
        )
        return {
            "booking_id": booking.id,
            "interviewer_id": booking.interviewer_id,
            "candidate_id": booking.candidate_id,
            "start": to_canonical(booking.start),
            "end": to_canonical(booking.end),
            "hold_id": str(args["hold_id"]),
        }
    if name == "cancel_booking":
        booking = ctx.calendar.cancel(
            str(args["booking_id"]), str(args["candidate_id"])
        )
        return {
            "booking_id": booking.id,
            "status": booking.status,
            "interviewer_id": booking.interviewer_id,
            "start": to_canonical(booking.start),
            "end": to_canonical(booking.end),
        }
    raise CalendarError("UNKNOWN_TOOL", name)
