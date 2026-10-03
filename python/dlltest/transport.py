"""Transports that connect the test harness to the DLL.

The tests use only the DllTransport interface. PipeTransport speaks the v1
named pipe. A TcpTransport for protocol v2 replaces it later without changes
to the tests.
"""

from __future__ import annotations

import queue
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable, Optional

from orchestrator import message_logger
from orchestrator.pipe_server import NamedPipeServer

PIPE_NAME = "\\\\.\\pipe\\civv_llm"
LOG_DIR = Path(__file__).resolve().parent.parent / "logs" / "dlltest"

# Pushed into the event queue when the DLL goes away, so a waiting test
# fails at once instead of at its timeout.
_DISCONNECTED = "_disconnected"


class TransportError(Exception):
    """The DLL did not answer, went away, or could not be reached."""


class DllTransport(ABC):
    """Request/response plus pushed events, independent of the wire."""

    @abstractmethod
    def start(self) -> None:
        """Start listening for the DLL."""

    @abstractmethod
    def wait_connected(self, timeout: float) -> None:
        """Block until the DLL connects. Raise TransportError on timeout."""

    @abstractmethod
    def request(self, message: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
        """Send a command and return the DLL's response to it."""

    @abstractmethod
    def next_event(
        self, types: Optional[Iterable[str]] = None, timeout: float = 10.0
    ) -> dict[str, Any]:
        """Return the next pushed event, skipping types not in `types`."""

    @abstractmethod
    def stop(self) -> None:
        """Close the connection."""


class _EventPipeServer(NamedPipeServer):
    """NamedPipeServer that hands pushed events to a queue."""

    def __init__(self, pipe_name: str, events: "queue.Queue[dict[str, Any]]"):
        super().__init__(pipe_name, broadcaster=None)
        self._events = events
        self.startup_error: Optional[str] = None
        self.startup_failed = threading.Event()

    def _process_message(self, message: dict[str, Any]) -> None:
        super()._process_message(message)
        self._events.put(message)

    def _create_pipe(self) -> int:
        try:
            return super()._create_pipe()
        except OSError as e:
            # Max instances is 1, so this fails when the orchestrator (or
            # another harness) already owns the pipe.
            self.startup_error = (
                f"Cannot create {self.pipe_name} ({e}). Another process owns the pipe. "
                "Stop the orchestrator (launch.py) before running the DLL tests."
            )
            self._running = False
            self.startup_failed.set()
            raise

    def _close(self) -> None:
        was_connected = self._connection_ready.is_set()
        super()._close()
        if was_connected:
            self._events.put({"type": _DISCONNECTED})


class PipeTransport(DllTransport):
    """v1 transport: the harness is the named pipe server, the DLL the client."""

    def __init__(self, pipe_name: str = PIPE_NAME):
        # The orchestrator's logger writes python/logs/game_{id}.jsonl. Point
        # it at a separate folder so test traffic stays out of real game logs.
        message_logger._instance = message_logger.MessageLogger(log_dir=LOG_DIR)
        self._events: "queue.Queue[dict[str, Any]]" = queue.Queue()
        self._server = _EventPipeServer(pipe_name, self._events)
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._server.start, name="dlltest-pipe", daemon=True)
        self._thread.start()

    def wait_connected(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._server.startup_failed.is_set():
                raise TransportError(self._server.startup_error)
            if self._server.get_pipe_connection(timeout=0.25):
                return
        raise TransportError(
            f"The DLL did not connect within {timeout:.0f}s. Start Civ V with the "
            "Community Patch mod and load a test save (see python/dlltest/saves.yaml)."
        )

    def request(self, message: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
        msg_type = message.get("type")
        try:
            response = self._server.send_request(dict(message), timeout=timeout)
        except RuntimeError as e:
            raise TransportError(f"{msg_type}: {e}") from e
        if response.get("status") == "timeout":
            raise TransportError(f"{msg_type}: no response within {timeout:.0f}s")
        if response.get("error") == "Pipe write failed":
            raise TransportError(f"{msg_type}: pipe write failed (DLL disconnected?)")
        return response

    def next_event(
        self, types: Optional[Iterable[str]] = None, timeout: float = 10.0
    ) -> dict[str, Any]:
        wanted = set(types) if types is not None else None
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportError(f"No {sorted(wanted) if wanted else 'event'} within {timeout:.0f}s")
            try:
                event = self._events.get(timeout=remaining)
            except queue.Empty:
                continue
            if event.get("type") == _DISCONNECTED:
                raise TransportError("DLL disconnected")
            if wanted is None or event.get("type") in wanted:
                return event

    def stop(self) -> None:
        self._server.stop()
