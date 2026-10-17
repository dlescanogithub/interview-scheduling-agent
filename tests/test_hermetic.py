"""The suite must not call a provider or open a socket."""

from __future__ import annotations

import os
import socket

import pytest

from scheduling_agent.live import UrllibTransport


def test_live_env_is_cleared() -> None:
    for name in (
        "LIVE_LLM",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "XAI_API_KEY",
        "MAX_LIVE_SPEND_USD",
    ):
        assert os.environ.get(name) in (None, "")


def test_socket_guard_blocks_a_provider_call() -> None:
    with pytest.raises(BaseException, match="network"):
        socket.create_connection(("203.0.113.5", 9), timeout=0.05)
    with pytest.raises(BaseException, match="network"):
        UrllibTransport().post(
            "http://203.0.113.5:9/v1/chat/completions",
            {},
            {"messages": []},
            timeout=0.05,
        )
