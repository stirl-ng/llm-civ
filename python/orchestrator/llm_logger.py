"""JSONL file logger for LLM API requests and responses."""

import json
import threading
from pathlib import Path
from typing import Any, Optional

# Module-level singleton instance
_instance: Optional["LLMLogger"] = None
_instance_lock = threading.Lock()


def get_llm_logger() -> "LLMLogger":
    """Get the singleton LLMLogger instance."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = LLMLogger()
    return _instance


class LLMLogger:
    """JSONL file logger for LLM API requests and responses.
    
    Logs all LLM API calls (requests and responses) to a separate JSONL file
    for debugging and analysis. This is separate from tool call logs.
    """

    def __init__(self, messages_file: str = "logs/llm_messages.jsonl"):
        """Initialize the LLM logger.
        
        Args:
            messages_file: Path to JSONL file for LLM API messages
        """
        self.messages_file = Path(messages_file)
        self._lock = threading.Lock()
        
        # Ensure directory exists
        self.messages_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Ensure file exists
        self.messages_file.touch(exist_ok=True)

    def log_request(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """Log an LLM API request.
        
        Args:
            model: Model name/identifier
            messages: Chat messages sent to LLM
            **kwargs: Additional request parameters (temperature, etc.)
        
        Returns:
            UUID of the logged request (for correlating with response)
        """
        from datetime import datetime
        from uuid import uuid4
        
        request_uuid = str(uuid4())
        log_entry = {
            "type": "llm_request",
            "timestamp": datetime.now().isoformat(),
            "uuid": request_uuid,
            "model": model,
            "messages": messages,
            **kwargs,
        }
        
        with self._lock:
            with open(self.messages_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        
        return request_uuid

    def log_response(self, request_uuid: str, response: str, **kwargs: Any) -> None:
        """Log an LLM API response.
        
        Args:
            request_uuid: UUID of the corresponding request
            response: Response text from LLM
            **kwargs: Additional response metadata
        """
        from datetime import datetime
        
        log_entry = {
            "type": "llm_response",
            "timestamp": datetime.now().isoformat(),
            "request_uuid": request_uuid,
            "response": response,
            **kwargs,
        }
        
        with self._lock:
            with open(self.messages_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")

