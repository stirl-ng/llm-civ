"""
MCP Server for Civilization V LLM Orchestrator

Provides tools for LLMs to:
- Query game state (cached from turn start)
- Send actions immediately to the DLL (synchronous, with response)
- End their turn when done deciding

Each action is sent immediately to the DLL and the response is returned
to the LLM, allowing it to see the result before deciding the next action.
"""

import logging
import threading
from typing import TYPE_CHECKING, Any, Optional

from .formatting import format_game_state

if TYPE_CHECKING:
    from .pipe_server import PipeConnection

logger = logging.getLogger(__name__)


# Tool definitions for documentation/discovery
AVAILABLE_TOOLS = [
    {
        "name": "get_game_state",
        "description": "Get the current game state. Optionally filter by category.",
        "parameters": ["category", "format"],
    },
    {
        "name": "send_action",
        "description": "Send an action to the game immediately and get the result.",
        "parameters": ["action"],
    },
    {
        "name": "get_cities",
        "description": "Get detailed information about all cities.",
        "parameters": ["city_id"],
    },
    {
        "name": "get_units",
        "description": "Get information about all units.",
        "parameters": ["unit_id"],
    },
    {
        "name": "get_tech_tree",
        "description": "Get technology tree status.",
        "parameters": [],
    },
    {
        "name": "get_diplomacy",
        "description": "Get diplomatic status with all known civilizations.",
        "parameters": [],
    },
    {
        "name": "get_available_choices",
        "description": "Get all pending decisions (tech, policy, production, etc.)",
        "parameters": [],
    },
    {
        "name": "get_victory_progress",
        "description": "Get progress toward all victory conditions.",
        "parameters": [],
    },
    {
        "name": "get_resources",
        "description": "Get strategic and luxury resources.",
        "parameters": [],
    },
    {
        "name": "format_state",
        "description": "Get a human-readable formatted version of the game state.",
        "parameters": ["raw"],
    },
    {
        "name": "end_turn",
        "description": "Signal that you are done with your turn.",
        "parameters": ["notes"],
    },
]


class CivMCPServer:
    """Tool executor that bridges LLM requests to Civ V game.

    Sequential turn flow:
    1. Orchestrator calls start_turn(state, pipe_connection)
    2. LLM queries state and sends actions via tools
    3. Each action is sent immediately to DLL, response returned to LLM
    4. LLM calls end_turn when done
    5. Orchestrator resumes, signals DLL to advance turn
    """

    def __init__(self, turn_timeout: float = 300.0):
        """Initialize the MCP server.

        Args:
            turn_timeout: Max seconds to wait for LLM to end turn (default 5 min)
        """
        self.current_state: Optional[dict[str, Any]] = None
        self.turn_timeout = turn_timeout

        # Pipe connection for sending actions (set during turn)
        self._pipe_conn: Optional["PipeConnection"] = None

        # Turn management
        self._turn_active = False
        self._turn_ended = threading.Event()
        self._turn_notes: str = ""
        self._lock = threading.Lock()

    def start_turn(self, state: dict[str, Any], pipe_conn: "PipeConnection") -> None:
        """Start a new turn with the given game state and pipe connection.

        Args:
            state: Game state from DLL
            pipe_conn: PipeConnection for sending actions to DLL
        """
        with self._lock:
            self.current_state = state
            self._pipe_conn = pipe_conn
            self._turn_notes = ""
            self._turn_ended.clear()
            self._turn_active = True

        turn_num = state.get("turn", "?")
        logger.info(f"Turn {turn_num} started - waiting for LLM decisions")

    def wait_for_turn_end(self, timeout: Optional[float] = None) -> bool:
        """Block until LLM calls end_turn or timeout expires.

        Args:
            timeout: Max seconds to wait (uses self.turn_timeout if None)

        Returns:
            True if turn ended normally, False if timed out
        """
        wait_time = timeout if timeout is not None else self.turn_timeout
        ended = self._turn_ended.wait(timeout=wait_time)

        with self._lock:
            self._turn_active = False
            self._pipe_conn = None

        if not ended:
            logger.warning(f"Turn timed out after {wait_time}s")

        return ended

    def get_turn_notes(self) -> str:
        """Get notes from the completed turn."""
        with self._lock:
            return self._turn_notes

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool and return results."""

        if name == "get_game_state":
            return self._get_game_state(
                category=arguments.get("category"),
                format_type=arguments.get("format", "json")
            )

        elif name == "send_action":
            return self._send_action(action=arguments.get("action", {}))

        elif name == "get_cities":
            return self._get_cities(city_id=arguments.get("city_id"))

        elif name == "get_units":
            return self._get_units(unit_id=arguments.get("unit_id"))

        elif name == "get_tech_tree":
            return self._get_tech_tree()

        elif name == "get_diplomacy":
            return self._get_diplomacy()

        elif name == "get_available_choices":
            return self._get_available_choices()

        elif name == "get_victory_progress":
            return self._get_victory_progress()

        elif name == "get_resources":
            return self._get_resources()

        elif name == "format_state":
            return self._format_state(raw=arguments.get("raw", False))

        elif name == "end_turn":
            return self._end_turn(notes=arguments.get("notes", ""))

        else:
            return {"error": f"Unknown tool: {name}"}

    def _send_action(self, action: dict[str, Any]) -> dict[str, Any]:
        """Send an action to the DLL immediately and return the response."""
        with self._lock:
            if not self._turn_active:
                return {"error": "Cannot send action - no active turn"}
            pipe_conn = self._pipe_conn

        if not pipe_conn:
            return {"error": "No pipe connection available"}

        logger.info(f"Sending action to DLL: {action}")

        # Send action and get response synchronously
        response = pipe_conn.send_action({"type": "action", "action": action})

        logger.info(f"DLL response: {response}")

        # Update current state if response includes updated state
        if "state" in response:
            with self._lock:
                if self.current_state:
                    self.current_state["state"] = response["state"]

        return response

    def _end_turn(self, notes: str = "") -> dict[str, Any]:
        """Signal that the LLM is done with its turn."""
        with self._lock:
            if not self._turn_active:
                return {"error": "No active turn to end"}

            self._turn_notes = notes
            pipe_conn = self._pipe_conn

        # Send end_turn to DLL
        if pipe_conn:
            pipe_conn.send_end_turn()

        # Signal orchestrator that turn is done
        self._turn_ended.set()

        logger.info(f"Turn ended by LLM")
        return {
            "status": "turn_ended",
            "notes": notes
        }

    def _get_game_state(self, category: Optional[str] = None, format_type: str = "json") -> dict[str, Any]:
        """Get current game state, optionally filtered by category."""
        if not self.current_state:
            return {"error": "No game state available - not your turn yet"}

        state = self.current_state.get("state", {})

        if category:
            if category in state:
                state = {category: state[category]}
            else:
                return {"error": f"Category '{category}' not found", "available": list(state.keys())}

        if format_type == "human_readable":
            formatted = format_game_state(state)
            return {"formatted": formatted, "json": state}

        return state

    def _get_cities(self, city_id: Optional[int] = None) -> dict[str, Any]:
        """Get city information."""
        if not self.current_state:
            return {"error": "No game state available"}

        cities = self.current_state.get("state", {}).get("cities", [])

        if city_id is not None:
            city = next((c for c in cities if c.get("id") == city_id), None)
            if city:
                return city
            return {"error": f"City {city_id} not found"}

        return {"cities": cities, "count": len(cities)}

    def _get_units(self, unit_id: Optional[int] = None) -> dict[str, Any]:
        """Get unit information."""
        if not self.current_state:
            return {"error": "No game state available"}

        units = self.current_state.get("state", {}).get("units", [])

        if unit_id is not None:
            unit = next((u for u in units if u.get("id") == unit_id), None)
            if unit:
                return unit
            return {"error": f"Unit {unit_id} not found"}

        return {"units": units, "count": len(units)}

    def _get_tech_tree(self) -> dict[str, Any]:
        """Get technology tree information."""
        if not self.current_state:
            return {"error": "No game state available"}

        return self.current_state.get("state", {}).get("technology", {})

    def _get_diplomacy(self) -> dict[str, Any]:
        """Get diplomacy information."""
        if not self.current_state:
            return {"error": "No game state available"}

        return self.current_state.get("state", {}).get("diplomacy", {})

    def _get_available_choices(self) -> dict[str, Any]:
        """Get all pending choices/decisions."""
        if not self.current_state:
            return {"error": "No game state available"}

        data = self.current_state.get("state", {})
        choices = {}

        if data.get("needs_tech_choice"):
            choices["tech"] = data.get("available_techs", [])

        if data.get("needs_policy_choice"):
            choices["policy"] = data.get("available_policies", [])

        if data.get("needs_production_choice"):
            choices["production"] = data.get("cities_needing_production", [])

        if data.get("needs_religion_choice"):
            choices["religion"] = data.get("religion_options", {})

        if data.get("needs_trade_route_assignment"):
            choices["trade_routes"] = data.get("available_trade_routes", [])

        return {"pending_choices": choices, "has_choices": len(choices) > 0}

    def _get_victory_progress(self) -> dict[str, Any]:
        """Get victory condition progress."""
        if not self.current_state:
            return {"error": "No game state available"}

        data = self.current_state.get("state", {})
        return {
            "victory_conditions": data.get("victory_conditions", []),
            "victory_progress": data.get("victory_progress", {})
        }

    def _get_resources(self) -> dict[str, Any]:
        """Get resource information."""
        if not self.current_state:
            return {"error": "No game state available"}

        data = self.current_state.get("state", {})
        return {
            "strategic": data.get("strategic_resources", {}),
            "luxury": data.get("luxury_resources", {}),
            "total": data.get("resources", {})
        }

    def _format_state(self, raw: bool = False) -> dict[str, Any]:
        """Get formatted game state."""
        if not self.current_state:
            return {"error": "No game state available"}

        data = self.current_state.get("state", {})
        formatted = format_game_state(data)

        if raw:
            return {"formatted": formatted, "raw": data}

        return {"formatted": formatted}
