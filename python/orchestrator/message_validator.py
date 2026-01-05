"""Message validation and sanity checking for incoming DLL messages."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MessageValidator:
    """Validates and performs sanity checks on DLL messages."""

    @staticmethod
    def validate_message(message: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate a DLL message.
        
        Args:
            message: Message dictionary to validate
            
        Returns:
            Tuple of (is_valid, error_message). If valid, error_message is None.
        """
        if not isinstance(message, dict):
            return False, f"Message must be a dictionary, got {type(message).__name__}"
        
        if not message:
            return False, "Message cannot be empty"
        
        # Check for required message type
        msg_type = message.get("type")
        if not msg_type:
            return False, "Message missing required 'type' field"
        
        # Validate turn_start messages
        if msg_type == "turn_start":
            return MessageValidator._validate_turn_start(message)
        
        # Validate action_result messages
        if msg_type == "action_result":
            return MessageValidator._validate_action_result(message)
        
        # Other message types are allowed but logged
        logger.debug(f"Received message type '{msg_type}' (not specifically validated)")
        return True, None

    @staticmethod
    def _validate_turn_start(message: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate a turn_start message."""
        # Check required fields
        if "turn" not in message:
            return False, "turn_start message missing 'turn' field"
        
        if "player_id" not in message:
            return False, "turn_start message missing 'player_id' field"
        
        if "state" not in message:
            return False, "turn_start message missing 'state' field"
        
        turn = message.get("turn")
        player_id = message.get("player_id")
        state_data = message.get("state", {})
        
        # Sanity checks
        if not isinstance(turn, int):
            return False, f"turn must be an integer, got {type(turn).__name__}"
        
        if turn < 0:
            return False, f"turn must be non-negative, got {turn}"
        
        if not isinstance(player_id, int):
            return False, f"player_id must be an integer, got {type(player_id).__name__}"
        
        if player_id < 0:
            return False, f"player_id must be non-negative, got {player_id}"
        
        if not isinstance(state_data, dict):
            return False, f"state field must be a dictionary, got {type(state_data).__name__}"
        
        # Validate state structure
        errors = MessageValidator._validate_state_structure(state_data)
        if errors:
            return False, f"State structure validation failed: {', '.join(errors)}"
        
        return True, None

    @staticmethod
    def _validate_action_result(message: dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate an action_result message."""
        if "request_id" not in message:
            return False, "action_result message missing 'request_id' field"
        
        if "success" not in message:
            return False, "action_result message missing 'success' field"
        
        success = message.get("success")
        if not isinstance(success, bool):
            return False, f"success must be a boolean, got {type(success).__name__}"
        
        return True, None

    @staticmethod
    def _validate_state_structure(state: dict[str, Any]) -> list[str]:
        """Validate the structure of the inner state object.
        
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        
        # Check for common expected fields (warn but don't fail)
        expected_fields = ["turn", "playersAlive", "civsEver"]
        for field in expected_fields:
            if field not in state:
                logger.debug(f"State missing expected field '{field}'")
        
        # Validate turn if present
        if "turn" in state:
            turn = state["turn"]
            if not isinstance(turn, int):
                errors.append(f"state.turn must be integer, got {type(turn).__name__}")
            elif turn < 0:
                errors.append(f"state.turn must be non-negative, got {turn}")
        
        # Validate playersAlive if present
        if "playersAlive" in state:
            players = state["playersAlive"]
            if not isinstance(players, int):
                errors.append(f"state.playersAlive must be integer, got {type(players).__name__}")
            elif players < 0:
                errors.append(f"state.playersAlive must be non-negative, got {players}")
        
        # Validate cities if present
        if "cities" in state:
            cities = state["cities"]
            if not isinstance(cities, list):
                errors.append(f"state.cities must be a list, got {type(cities).__name__}")
        
        # Validate units if present
        if "units" in state:
            units = state["units"]
            if not isinstance(units, list):
                errors.append(f"state.units must be a list, got {type(units).__name__}")
        
        return errors

    @staticmethod
    def check_turn_consistency(
        previous_message: Optional[dict[str, Any]],
        new_message: dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """Check consistency between previous and new turn_start messages.
        
        Args:
            previous_message: Previous turn_start message (if available)
            new_message: New turn_start message to check
            
        Returns:
            Tuple of (is_consistent, warning_message). Warning is None if consistent.
        """
        if not previous_message:
            return True, None
        
        prev_turn = previous_message.get("turn")
        new_turn = new_message.get("turn")
        
        if prev_turn is not None and new_turn is not None:
            if new_turn < prev_turn:
                return False, f"Turn number decreased from {prev_turn} to {new_turn}"
            if new_turn > prev_turn + 1:
                return False, f"Turn number jumped from {prev_turn} to {new_turn} (expected {prev_turn + 1})"
        
        prev_player = previous_message.get("player_id")
        new_player = new_message.get("player_id")
        
        if prev_player is not None and new_player is not None:
            if new_player != prev_player:
                # This is OK if it's a different player's turn
                logger.debug(f"Player changed from {prev_player} to {new_player}")
        
        return True, None

