"""Persistent knowledge base for long-term memory storage."""

import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional


class KnowledgeBase:
    """Simple key-value store for persistent long-term memory.
    
    Similar to Pokemon's XML sections, stores structured information
    that persists across turns and sessions.
    
    Thread-safe for concurrent access.
    """

    def __init__(self, storage_file: str = "logs/knowledge_base.json"):
        """Initialize the knowledge base.
        
        Args:
            storage_file: Path to JSON file for persistent storage
        """
        self.storage_file = Path(storage_file)
        self._lock = threading.Lock()
        self._data: Dict[str, str] = {}
        
        # Ensure directory exists
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing data if file exists
        self._load()

    def _load(self) -> None:
        """Load data from storage file."""
        if self.storage_file.exists():
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                # If file is corrupted or can't be read, start fresh
                self._data = {}

    def _save(self) -> None:
        """Save data to storage file."""
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except IOError:
            # If save fails, log but don't crash
            pass

    def get(self, section_id: str) -> Optional[str]:
        """Get content for a section.
        
        Args:
            section_id: Identifier for the section
            
        Returns:
            Content string if section exists, None otherwise
        """
        with self._lock:
            return self._data.get(section_id)

    def set(self, section_id: str, content: str) -> None:
        """Set content for a section (add or update).
        
        Args:
            section_id: Identifier for the section
            content: Content to store
        """
        with self._lock:
            self._data[section_id] = content
            self._save()

    def delete(self, section_id: str) -> bool:
        """Delete a section.
        
        Args:
            section_id: Identifier for the section
            
        Returns:
            True if section was deleted, False if it didn't exist
        """
        with self._lock:
            if section_id in self._data:
                del self._data[section_id]
                self._save()
                return True
            return False

    def list_all(self) -> Dict[str, str]:
        """Get all sections.
        
        Returns:
            Dictionary of all section_id -> content mappings
        """
        with self._lock:
            return self._data.copy()

    def has(self, section_id: str) -> bool:
        """Check if a section exists.
        
        Args:
            section_id: Identifier for the section
            
        Returns:
            True if section exists, False otherwise
        """
        with self._lock:
            return section_id in self._data

