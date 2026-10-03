"""Session fixtures: connect to the DLL once and check the right save is loaded."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pytest
import yaml

from dlltest.transport import DllTransport, PipeTransport, TransportError

SAVES_FILE = Path(__file__).resolve().parent / "saves.yaml"

# Events that carry game identity. The DLL sends turn_start and game_start once
# per game load, on the first connect; after that only the heartbeat (every 5 s).
_IDENTITY_EVENTS = ("turn_start", "game_start", "heartbeat")


@dataclass(frozen=True)
class Game:
    save: str
    game_id: int
    player_id: int
    turn: int
    info: dict[str, Any]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--connect-timeout", type=float, default=30.0,
        help="Seconds to wait for the DLL to connect (default 30).",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "smoke: fast per-command checks against a loaded test save")
    config.addinivalue_line("markers", "snapshot: compare read responses with stored copies")
    config.addinivalue_line("markers", "soak: end many turns and watch for crashes or hangs")


def _identify(transport: DllTransport) -> Game:
    try:
        event = transport.next_event(types=_IDENTITY_EVENTS, timeout=12)
    except TransportError as e:
        pytest.exit(f"Could not identify the loaded game: {e}", returncode=3)

    game_id, turn = event.get("game_id"), event.get("turn")
    saves: dict[str, dict[str, Any]] = yaml.safe_load(SAVES_FILE.read_text())["saves"]
    for name, info in saves.items():
        if info["game_id"] == game_id:
            if info["turn"] != turn:
                pytest.exit(
                    f"Save 'dlltest_{name}' starts on turn {info['turn']}, but the game is on turn {turn}. "
                    "Reload it and run again.",
                    returncode=3,
                )
            return Game(name, game_id, event.get("player_id"), turn, info)

    known = ", ".join(f"'dlltest_{name}'" for name in saves)
    pytest.exit(
        f"The loaded game (game_id {game_id}, turn {turn}) is not a known test save. "
        f"Load one of {known} from Mods > Next > Load Game (install them with "
        f"scripts/install-test-saves.ps1). For a new save, add it to {SAVES_FILE.name}.",
        returncode=3,
    )


@pytest.fixture(scope="session")
def _connection(pytestconfig: pytest.Config):
    transport = PipeTransport()
    transport.start()
    try:
        transport.wait_connected(pytestconfig.getoption("--connect-timeout"))
    except TransportError as e:
        transport.stop()
        pytest.exit(str(e), returncode=3)
    game = _identify(transport)
    yield transport, game
    transport.stop()


@pytest.fixture(scope="session")
def dll(_connection) -> DllTransport:
    return _connection[0]


@pytest.fixture(scope="session")
def game(_connection) -> Game:
    return _connection[1]


@pytest.fixture(scope="session")
def call(dll: DllTransport) -> Callable[..., dict[str, Any]]:
    """Send a command and assert that the DLL answered with `result_type`."""

    def _call(msg_type: str, result_type: str, **args: Any) -> dict[str, Any]:
        response = dll.request({"type": msg_type, **args})
        assert response.get("type") != "error", f"{msg_type} returned an error: {response}"
        assert response.get("type") == result_type, (
            f"{msg_type}: expected type '{result_type}', got '{response.get('type')}'"
        )
        return response

    return _call
