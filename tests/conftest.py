"""Keep the suite off the network and off a live provider.

An exported LIVE_LLM=1 used to make the live CLI and the dotenv loader
read a real key. Every test starts from a scripted environment.
"""

from __future__ import annotations

import os
import socket

import pytest

_LIVE_EXACT = (
    "LIVE_LLM",
    "XAI_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "OPENAI_API_BASE",
    "MAX_LIVE_SPEND_USD",
    "MAX_LIVE_TOKENS",
)


class SuiteNetworkCall(BaseException):
    """A test tried to open a socket.

    This is a BaseException so urllib and the retry helper, which catch
    Exception, cannot turn a real call into a provider error and continue.
    """


def _refuse_network(*_args: object, **_kwargs: object) -> None:
    raise SuiteNetworkCall("the test suite attempted a network call")


class _GuardedSocket(socket.socket):
    def connect(self, address: object, /) -> None:  # type: ignore[override]
        raise SuiteNetworkCall(f"the test suite attempted a network call: {address!r}")

    def connect_ex(self, address: object, /) -> int:  # type: ignore[override]
        raise SuiteNetworkCall(f"the test suite attempted a network call: {address!r}")


def _noop_dotenv(path: object = None) -> None:
    """Ignore a developer .env. Tests that load a fixture call the real loader."""
    del path


@pytest.fixture(autouse=True)
def isolate_live_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop live credentials and force the scripted provider."""
    for name in list(os.environ):
        if name in _LIVE_EXACT or name.startswith(("LLM_", "XAI_")):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("scheduling_agent.cli.load_dotenv_file", _noop_dotenv)
    monkeypatch.setattr(socket, "socket", _GuardedSocket)
    monkeypatch.setattr(socket, "create_connection", _refuse_network)
    monkeypatch.setattr(socket, "getaddrinfo", _refuse_network)
