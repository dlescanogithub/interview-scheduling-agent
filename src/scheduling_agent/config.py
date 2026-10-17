"""Environment-only configuration. Nothing here is a vendor price list."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv_file(path: Path | None = None) -> None:
    """Load KEY=VALUE lines into the environment without overriding exports.

    Missing files are ignored. Values are never logged.
    """
    env_path = path if path is not None else Path(".env")
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _optional_float(name: str) -> float | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    return float(raw)


def _optional_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    return int(raw)


@dataclass(frozen=True)
class Settings:
    """Process settings. Live fields stay empty unless the operator exports them."""

    max_turns: int = 8
    max_tool_calls: int = 16
    per_tool_cap: int = 6
    max_cost_usd: float = 1.0
    sim_price_in_per_mtok: float = 0.0
    sim_price_out_per_mtok: float = 0.0
    max_output_tokens_reservation: int = 200
    hold_ttl_seconds: int = 900
    approval_ttl_seconds: int = 86_400
    retry_attempts: int = 3
    retry_base_seconds: float = 0.01
    retry_cap_seconds: float = 0.05
    external_tools_enabled: bool = True
    bypass_gates: bool = False
    retrieval_threshold: float = 1.0
    retrieval_k: int = 3
    now_iso: str = "2026-04-13T12:00:00+00:00"
    live_llm: bool = False
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    llm_model_scheduler: str = ""
    llm_max_output_tokens: int = 512
    max_live_spend_usd: float | None = None
    max_live_tokens: int | None = None
    llm_price_in_per_mtok: float | None = None
    llm_price_out_per_mtok: float | None = None

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            max_turns=int(os.environ.get("MAX_TURNS", "8")),
            max_tool_calls=int(os.environ.get("MAX_TOOL_CALLS", "16")),
            max_cost_usd=float(os.environ.get("MAX_COST_USD", "1")),
            sim_price_in_per_mtok=float(os.environ.get("SIM_PRICE_IN_PER_MTOK", "0")),
            sim_price_out_per_mtok=float(os.environ.get("SIM_PRICE_OUT_PER_MTOK", "0")),
            hold_ttl_seconds=int(os.environ.get("HOLD_TTL_SECONDS", "900")),
            approval_ttl_seconds=int(os.environ.get("APPROVAL_TTL_SECONDS", "86400")),
            external_tools_enabled=_flag("EXTERNAL_TOOLS_ENABLED", True),
            live_llm=_flag("LIVE_LLM", False),
            llm_base_url=os.environ.get("LLM_BASE_URL", ""),
            llm_api_key=os.environ.get("LLM_API_KEY", ""),
            llm_model=os.environ.get("LLM_MODEL", ""),
            llm_model_scheduler=os.environ.get("LLM_MODEL_SCHEDULER", ""),
            llm_max_output_tokens=int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "512")),
            max_live_spend_usd=_optional_float("MAX_LIVE_SPEND_USD"),
            max_live_tokens=_optional_int("MAX_LIVE_TOKENS"),
            llm_price_in_per_mtok=_optional_float("LLM_PRICE_IN_PER_MTOK"),
            llm_price_out_per_mtok=_optional_float("LLM_PRICE_OUT_PER_MTOK"),
        )

    def scheduler_model(self) -> str:
        return self.llm_model_scheduler or self.llm_model


class LiveConfigError(ValueError):
    """Live mode refused to start. The message must already be redacted."""


def assert_live_ready(settings: Settings) -> None:
    """Refuse to start a live run when the spend cap or prices are unusable."""
    if not settings.live_llm:
        raise LiveConfigError("LIVE_LLM is not enabled")
    if settings.max_live_spend_usd is None or settings.max_live_spend_usd <= 0:
        raise LiveConfigError("MAX_LIVE_SPEND_USD is required and must be > 0")
    if not settings.llm_base_url or not settings.llm_api_key or not settings.llm_model:
        raise LiveConfigError("LLM_BASE_URL, LLM_API_KEY and LLM_MODEL are required")
    prices_set = (
        settings.llm_price_in_per_mtok is not None
        and settings.llm_price_out_per_mtok is not None
    )
    if not prices_set and (
        settings.max_live_tokens is None or settings.max_live_tokens <= 0
    ):
        raise LiveConfigError(
            "LLM_PRICE_IN_PER_MTOK and LLM_PRICE_OUT_PER_MTOK are unset; "
            "set them or set MAX_LIVE_TOKENS"
        )
