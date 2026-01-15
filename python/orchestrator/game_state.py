"""GameState - Single source of truth for game metadata.

Thread-safe class that holds game metadata (turn, game_id, session_id, etc.)
Updated by StateProcessor from DLL messages, read by CivMCPServer and Dashboard API.
"""

import threading
import time
from typing import Any, Optional


class GameState:
    """Thread-safe game state metadata storage.
    
    Serves as the single source of truth for game metadata. Updated by StateProcessor
    when processing DLL messages, read by CivMCPServer and Dashboard API.
    """

    def __init__(self):
        """Initialize empty game state."""
        self._lock = threading.Lock()
        
        # Turn management
        self._turn_number: Optional[int] = None
        
        # Session tracking (game_id persists across saves, session_id per connection)
        self._game_id: Optional[int] = None
        self._session_id: Optional[int] = None
        self._player_id: Optional[int] = None
        self._player_name: Optional[str] = None
        
        # Connection status
        self._connected: bool = False
        
        # Last update timestamp
        self._last_update_time: float = 0.0

    def update_from_message(self, state: dict[str, Any]) -> None:
        """Update state from message.
        
        Args:
            state: Game state dictionary from DLL message
        """
        with self._lock:
            # Update session tracking
            if not self._connected:
                self._connected = True
            
            if "turn" in state:
                if self._turn_number != state.get("turn"):
                    print('turn changed', self._turn_number, '->', state.get("turn"))
                    self._turn_number = state.get("turn")

            if "game_id" in state:
                if self._game_id != state.get("game_id"):
                    print('game_id changed', self._game_id, '->', state.get("game_id"))
                self._game_id = state.get("game_id")

            if "session_id" in state:
                if self._session_id != state.get("session_id"):
                    print('session_id changed', self._session_id, '->', state.get("session_id"))
                    self._session_id = state.get("session_id")

            if "player_id" in state:
                if self._player_id != state.get("player_id"):
                    print('player_id changed', self._player_id, '->', state.get("player_id"))
                    self._player_id = state.get("player_id")

            if "player_name" in state:
                if self._player_name != state.get("player_name"):
                    print('player_name changed', self._player_name, '->', state.get("player_name"))
                    self._player_name = state.get("player_name")
            
            # if "is_human" in state:
            #     if self._is_human != state.get("is_human"):
            #         print('is_human changed', self._is_human, '->', state.get("is_human"))
            #         self._is_human = state.get("is_human")

            # if "state" in state:
            #     if "playersAlive" in state.get("state"):
            #         if self._players_alive != state.get("state").get("playersAlive"):
            #             print('players_alive changed', self._players_alive, '->', state.get("state").get("playersAlive"))
            #             self._players_alive = state.get("state").get("playersAlive")
            #     if "civsEver" in state.get("state"):
            #         if self._civs_ever != state.get("state").get("civsEver"):
            #             print('civs_ever changed', self._civs_ever, '->', state.get("state").get("civsEver"))
            #             self._civs_ever = state.get("state").get("civsEver")

            self._last_update_time = time.time()

    def get_metadata(self) -> dict[str, Any]:
        """Get all metadata as dictionary.
        
        Returns:
            Dictionary containing all game state metadata
        """
        with self._lock:
            return {
                "turn_number": self._turn_number,
                "game_id": self._game_id,
                "session_id": self._session_id,
                "player_id": self._player_id,
                "player_name": self._player_name,
                "connected": self._connected,
                "last_update_time": self._last_update_time,
            }

    @property
    def turn_number(self) -> Optional[int]:
        """Current turn number."""
        with self._lock:
            return self._turn_number

    @property
    def game_id(self) -> Optional[int]:
        """Game ID (persists across saves)."""
        with self._lock:
            return self._game_id

    @property
    def session_id(self) -> Optional[int]:
        """Session ID (changes per pipe connection)."""
        with self._lock:
            return self._session_id

    @property
    def player_id(self) -> Optional[int]:
        """Current player ID."""
        with self._lock:
            return self._player_id

    @property
    def player_name(self) -> Optional[str]:
        """Current player name."""
        with self._lock:
            return self._player_name

    @property
    def connected(self) -> bool:
        """Whether pipe connection is active."""
        with self._lock:
            return self._connected

    @property
    def last_update_time(self) -> float:
        """Timestamp of last update."""
        with self._lock:
            return self._last_update_time

