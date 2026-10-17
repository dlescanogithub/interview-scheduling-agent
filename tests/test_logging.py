"""JSON logs redact secret-shaped strings and keep the required fields."""

from __future__ import annotations

import io
import json
import logging

import pytest

from scheduling_agent.clock import FixedClock
from scheduling_agent.logging_setup import JsonFormatter, configure_logging, log_event
from scheduling_agent.timeutil import parse_iso
from scheduling_agent.trace import Trace


def test_json_log_has_required_fields_and_redacts() -> None:
    stream = io.StringIO()
    logger = logging.getLogger("scheduling_agent_unit")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    secret = "sk" + "-" + "a1B2c3D4e5F6g7H8i9J0"
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        logger.exception(
            "saw %s",
            secret,
            extra={"run_id": "run-1", "fields": {"note": secret}},
        )
    payload = json.loads(stream.getvalue())
    assert payload["level"] == "ERROR"
    assert payload["run_id"] == "run-1"
    assert "ts" in payload and payload["ts"].endswith("Z")
    assert secret not in stream.getvalue()
    assert "[REDACTED:openai_key]" in payload["msg"]
    assert payload["note"].startswith("[REDACTED:")
    assert "exc" in payload


def test_configure_logging_is_idempotent(capsys: pytest.CaptureFixture[str]) -> None:
    logger = configure_logging(logging.INFO)
    log_event(logger, logging.INFO, "plain", "run-2", tool="search_faq")
    captured = capsys.readouterr()
    text = captured.err
    if text:
        row = json.loads(text.splitlines()[-1])
        assert row["msg"] == "plain"
        assert row["run_id"] == "run-2"
    again = configure_logging()
    assert again is logger


def test_trace_minimizes_email_and_secrets() -> None:
    clock = FixedClock(parse_iso("2026-04-13T12:00:00+00:00"))
    trace = Trace("run-1", clock)
    secret = "sk" + "-" + "a1B2c3D4e5F6g7H8i9J0"
    trace.add("user_message", text=f"write {secret} to ana.luz@taller-aurora.example")
    dumped = trace.to_jsonl()
    assert "ana.luz@taller-aurora.example" not in dumped
    assert "[email]" in dumped
    assert secret not in dumped
    assert trace.kinds() == ["user_message"]
