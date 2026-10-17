"""JSON logs with `ts`, `level`, `msg`, `run_id`, plus extra fields.

Secret-shaped strings are redacted with the vendored scanner patterns.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from scheduling_agent.secretscan import PATTERNS

_LOGGER_NAME = "scheduling_agent"


def redact(text: str) -> str:
    """Replace any secret-shaped substring. Returns the original when clean."""
    redacted = text
    for name, pattern in PATTERNS:
        redacted = pattern.sub(f"[REDACTED:{name}]", redacted)
    return redacted


class JsonFormatter(logging.Formatter):
    """One JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "level": record.levelname,
            "msg": redact(record.getMessage()),
            "run_id": getattr(record, "run_id", None),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(
                {str(key): _redact_value(value) for key, value in fields.items()}
            )
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _redact_value(value: object) -> object:
    if isinstance(value, str):
        return redact(value)
    return value


def configure_logging(level: int = logging.WARNING) -> logging.Logger:
    """Attach a single JSON handler. Safe to call more than once."""
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False
    if not any(
        isinstance(handler.formatter, JsonFormatter) for handler in logger.handlers
    ):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger


def log_event(
    logger: logging.Logger,
    level: int,
    msg: str,
    run_id: str,
    **fields: object,
) -> None:
    logger.log(level, redact(msg), extra={"run_id": run_id, "fields": fields})
