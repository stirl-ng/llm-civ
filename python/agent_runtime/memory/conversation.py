"""Conversation history management for agent runtime."""

from typing import Any, Dict, List, Optional


class ConversationHistory:
    """Track conversation history across turns.
    
    Stores messages per turn and supports summarization triggers.
    """

    def __init__(self, max_turns_before_summarize: int = 50):
        """Initialize conversation history.
        
        Args:
            max_turns_before_summarize: Number of turns before triggering summarization
        """
        self.max_turns_before_summarize = max_turns_before_summarize
        self._messages: List[Dict[str, Any]] = []
        self._last_summarized_turn: int = 0

    def add_message(self, role: str, content: str, turn: Optional[int] = None) -> None:
        """Add a message to the conversation history.
        
        Args:
            role: Message role ("system", "user", "assistant")
            content: Message content
            turn: Optional turn number for tracking
        """
        message = {
            "role": role,
            "content": content,
        }
        if turn is not None:
            message["turn"] = turn
        self._messages.append(message)

    def get_recent_messages(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent messages from conversation history.
        
        Args:
            limit: Maximum number of messages to return (None = all)
        
        Returns:
            List of message dicts
        """
        if limit is None:
            return self._messages.copy()
        return self._messages[-limit:]

    def get_all_messages(self) -> List[Dict[str, Any]]:
        """Get all messages in conversation history.
        
        Returns:
            List of all message dicts
        """
        return self._messages.copy()

    def should_summarize(self, turn_number: int) -> bool:
        """Check if conversation should be summarized.
        
        Args:
            turn_number: Current turn number
        
        Returns:
            True if summarization should be triggered
        """
        turns_since_summary = turn_number - self._last_summarized_turn
        return turns_since_summary >= self.max_turns_before_summarize

    def mark_summarized(self, turn_number: int) -> None:
        """Mark that conversation has been summarized at this turn.
        
        Args:
            turn_number: Turn number when summarization occurred
        """
        self._last_summarized_turn = turn_number

    def clear(self) -> None:
        """Clear all conversation history."""
        self._messages.clear()
        self._last_summarized_turn = 0

    def get_turn_messages(self, turn_number: int) -> List[Dict[str, Any]]:
        """Get all messages from a specific turn.
        
        Args:
            turn_number: Turn number to filter by
        
        Returns:
            List of message dicts from that turn
        """
        return [
            msg for msg in self._messages
            if msg.get("turn") == turn_number
        ]

