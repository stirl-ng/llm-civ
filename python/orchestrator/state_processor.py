"""State processor for handling incoming DLL messages.

Processes incoming messages from DLL - validates, logs, and routes to CivMCPServer.
"""

from typing import TYPE_CHECKING, Any, Optional

from .game_logger import get_game_logger
from .game_state import GameState
from .message_validator import MessageValidator

if TYPE_CHECKING:
    from .mcp_server import CivMCPServer


class StateProcessor:
    """Processes incoming messages from DLL - validates, logs, and routes to CivMCPServer."""

    def __init__(
        self, 
        mcp_server: Optional["CivMCPServer"] = None,
        game_state: Optional[GameState] = None
    ):
        """Initialize state processor.

        Args:
            mcp_server: CivMCPServer instance for turn management
            game_state: GameState instance to update from DLL messages
        """
        self.validator = MessageValidator()
        self._last_state: Optional[dict[str, Any]] = None
        self.mcp_server = mcp_server
        self.game_state = game_state

    def process_message(self, message: dict[str, Any]) -> None:
        """Process an incoming message from DLL.

        Logs everything, validates, and calls mcp_server on turn events.

        Args:
            message: Message dictionary from DLL
        """
        msg_type = message.get("type", "unknown")
        
        # Log messages from DLL to JSONL file (skip heartbeats to avoid spam)
        if msg_type != "heartbeat":
            log_msg = message.copy()
            log_msg["direction"] = "incoming"
            get_game_logger().log_message(log_msg)

        # Update game state from DLL messages
        if msg_type in ("turn_start", "heartbeat") and self.game_state:
            self.game_state.update_from_message(message)
        
        # Notifications and trace don't need further processing
        if msg_type in ("game_notification", "notification", "trace"):
            return

        # Validate message
        is_valid, error_msg = self.validator.validate_message(message)
        if not is_valid:
            return

        # Check consistency with previous turn_start
        if self._last_state:
            is_consistent, warning = self.validator.check_turn_consistency(self._last_state, message)

        self._last_state = message

