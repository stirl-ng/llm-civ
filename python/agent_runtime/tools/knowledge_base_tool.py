"""Tool wrapper for knowledge base operations."""

from typing import Any, Dict

from .base import Tool
from ..memory.knowledge_base import KnowledgeBase


class KnowledgeBaseTool(Tool):
    """Tool for managing knowledge base (long-term memory).
    
    Supports operations: add, update, delete, get, list
    """

    def __init__(self, knowledge_base: KnowledgeBase):
        """Initialize the knowledge base tool.
        
        Args:
            knowledge_base: KnowledgeBase instance to operate on
        """
        self.kb = knowledge_base

    def name(self) -> str:
        return "update_knowledge_base"

    def run(self, arguments: Dict[str, Any]) -> Any:
        """Execute knowledge base operation.
        
        Args:
            arguments: Dict with:
                - operation: "add" | "update" | "delete" | "get" | "list"
                - section_id: Section identifier (required for all except "list")
                - content: Content string (required for "add" and "update")
        
        Returns:
            Result dict with status and data
        """
        operation = arguments.get("operation", "").lower()
        
        if operation == "list":
            sections = self.kb.list_all()
            return {
                "status": "success",
                "sections": sections,
                "count": len(sections)
            }
        
        section_id = arguments.get("section_id")
        if not section_id:
            return {
                "status": "error",
                "error": "section_id is required for this operation"
            }
        
        if operation == "get":
            content = self.kb.get(section_id)
            if content is None:
                return {
                    "status": "error",
                    "error": f"Section '{section_id}' not found"
                }
            return {
                "status": "success",
                "section_id": section_id,
                "content": content
            }
        
        if operation == "delete":
            deleted = self.kb.delete(section_id)
            if deleted:
                return {
                    "status": "success",
                    "message": f"Section '{section_id}' deleted"
                }
            return {
                "status": "error",
                "error": f"Section '{section_id}' not found"
            }
        
        if operation in ("add", "update"):
            content = arguments.get("content")
            if content is None:
                return {
                    "status": "error",
                    "error": "content is required for add/update operations"
                }
            
            existed = self.kb.has(section_id)
            self.kb.set(section_id, content)
            
            if operation == "add" and existed:
                return {
                    "status": "success",
                    "message": f"Section '{section_id}' updated (already existed)"
                }
            elif operation == "update" and not existed:
                return {
                    "status": "success",
                    "message": f"Section '{section_id}' created (didn't exist)"
                }
            else:
                action = "created" if operation == "add" else "updated"
                return {
                    "status": "success",
                    "message": f"Section '{section_id}' {action}"
                }
        
        return {
            "status": "error",
            "error": f"Unknown operation: {operation}. Use: add, update, delete, get, list"
        }

