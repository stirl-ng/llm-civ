"""Enhanced strategy with knowledge base, briefing, and tool integration."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .base import Strategy
from ..briefing import generate_turn_briefing
from ..memory.conversation import ConversationHistory
from ..memory.knowledge_base import KnowledgeBase
from ..prompts.system_prompt import build_system_prompt


class EnhancedStrategy(Strategy):
    """Enhanced strategy with knowledge base, turn briefing, and tool integration.
    
    Maintains conversation history, uses turn briefing generator,
    integrates knowledge base, and supports tool calling.
    """

    def __init__(
        self,
        knowledge_base: Optional[KnowledgeBase] = None,
        conversation_history: Optional[ConversationHistory] = None,
        temperature: float = 0.2,
        max_tool_iterations: int = 10
    ):
        """Initialize enhanced strategy.
        
        Args:
            knowledge_base: Knowledge base instance for long-term memory
            conversation_history: Conversation history manager
            temperature: Model temperature for generation
            max_tool_iterations: Maximum tool call iterations per turn
        """
        self.kb = knowledge_base or KnowledgeBase()
        self.conversation = conversation_history or ConversationHistory()
        self.temperature = float(temperature)
        self.max_tool_iterations = max_tool_iterations

    def name(self) -> str:
        return f"enhanced@{self.temperature}"

    def decide(self, model: Any, tools: List[Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Produce actions for a turn using enhanced strategy.
        
        Args:
            model: Model adapter instance
            tools: List of available tools
            state: Game state dict (minimal, will query for details)
        
        Returns:
            Dict with 'actions' list and optional 'notes' string
        """
        turn_number = state.get("turn", 0)
        
        # Find MCP tool and KB tool
        mcp_tool = None
        kb_tool = None
        
        for tool in tools:
            tool_name = tool.name() if hasattr(tool, "name") else str(tool)
            if tool_name == "mcp_call":
                mcp_tool = tool
            elif tool_name == "update_knowledge_base":
                kb_tool = tool
        
        if not mcp_tool:
            # Fallback: return empty actions if no MCP tool
            return {"turn": turn_number, "actions": [], "notes": "No MCP tool available"}
        
        # Generate turn briefing
        briefing = generate_turn_briefing(mcp_tool, self.kb, turn_number)
        
        # Build system prompt
        system_prompt = build_system_prompt(tools, self.kb)
        
        # Build messages
        messages = self._build_messages(system_prompt, briefing, turn_number)
        
        # Generate response with tool calling support
        response_text = self._generate_with_tools(model, messages, tools, mcp_tool, kb_tool, turn_number)
        
        # Extract actions from response
        actions = self._extract_actions(response_text)
        
        # Try to update knowledge base from response
        if kb_tool:
            self._update_knowledge_base(response_text, kb_tool)
        
        # Add to conversation history
        self.conversation.add_message("user", briefing, turn=turn_number)
        self.conversation.add_message("assistant", response_text, turn=turn_number)
        
        return {
            "turn": turn_number,
            "actions": actions,
            "notes": response_text[:500] if response_text else ""  # Truncate notes
        }

    def _build_messages(
        self,
        system_prompt: str,
        briefing: str,
        turn_number: int
    ) -> List[Dict[str, str]]:
        """Build message list for model.
        
        Args:
            system_prompt: System prompt string
            briefing: Turn briefing string
            turn_number: Current turn number
        
        Returns:
            List of message dicts
        """
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add recent conversation history (last 10 messages)
        recent_messages = self.conversation.get_recent_messages(limit=10)
        for msg in recent_messages:
            # Skip messages from current turn (we're adding them now)
            if msg.get("turn") != turn_number:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Add current turn briefing
        messages.append({
            "role": "user",
            "content": briefing
        })
        
        return messages

    def _generate_with_tools(
        self,
        model: Any,
        messages: List[Dict[str, str]],
        tools: List[Any],
        mcp_tool: Any,
        kb_tool: Any,
        turn_number: int
    ) -> str:
        """Generate response with tool calling support.
        
        Args:
            model: Model adapter
            messages: Message list
            tools: Available tools
            mcp_tool: MCP tool instance
            kb_tool: Knowledge base tool instance
            turn_number: Current turn number
        
        Returns:
            Response text string
        """
        iteration = 0
        current_messages = messages.copy()
        
        while iteration < self.max_tool_iterations:
            # Generate response
            response = model.generate(current_messages, temperature=self.temperature)
            
            # Check for tool calls in response
            tool_calls = self._extract_tool_calls(response)
            
            if not tool_calls:
                # No tool calls, return response
                return response
            
            # Execute tool calls
            tool_results = []
            for tool_call in tool_calls:
                tool_name = tool_call.get("tool")
                tool_args = tool_call.get("arguments", {})
                
                # Route to appropriate tool
                if tool_name == "mcp_call":
                    result = mcp_tool.run(tool_args)
                elif tool_name == "update_knowledge_base" and kb_tool:
                    result = kb_tool.run(tool_args)
                else:
                    result = {"status": "error", "error": f"Unknown tool: {tool_name}"}
                
                tool_results.append({
                    "tool": tool_name,
                    "result": result
                })
            
            # Add tool results to conversation
            current_messages.append({
                "role": "assistant",
                "content": response
            })
            
            # Format tool results
            results_text = "\n".join([
                f"Tool {r['tool']} result: {json.dumps(r['result'], indent=2)}"
                for r in tool_results
            ])
            
            current_messages.append({
                "role": "user",
                "content": f"Tool execution results:\n{results_text}\n\nContinue with your response."
            })
            
            iteration += 1
        
        # If we hit max iterations, return last response
        return response

    def _extract_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """Extract tool calls from response text.
        
        Looks for patterns like:
        - mcp_call(tool="get_game_state", arguments={})
        - update_knowledge_base(operation="add", section_id="strategy", content="...")
        
        Args:
            text: Response text
        
        Returns:
            List of tool call dicts
        """
        tool_calls = []
        
        # Pattern for function calls
        pattern = r'(\w+)\(([^)]+)\)'
        
        for match in re.finditer(pattern, text):
            tool_name = match.group(1)
            args_str = match.group(2)
            
            # Try to parse arguments
            try:
                # Simple parsing - look for key="value" or key={...} patterns
                args = {}
                
                # Look for tool="..." pattern
                tool_match = re.search(r'tool\s*=\s*["\']([^"\']+)["\']', args_str)
                if tool_match:
                    args["tool"] = tool_match.group(1)
                
                # Look for arguments={...} pattern
                args_match = re.search(r'arguments\s*=\s*(\{[^}]+\})', args_str)
                if args_match:
                    try:
                        args["arguments"] = json.loads(args_match.group(1))
                    except json.JSONDecodeError:
                        pass
                
                # For knowledge base, parse operation, section_id, content
                if tool_name == "update_knowledge_base":
                    op_match = re.search(r'operation\s*=\s*["\']([^"\']+)["\']', args_str)
                    if op_match:
                        args["operation"] = op_match.group(1)
                    
                    sid_match = re.search(r'section_id\s*=\s*["\']([^"\']+)["\']', args_str)
                    if sid_match:
                        args["section_id"] = sid_match.group(1)
                    
                    content_match = re.search(r'content\s*=\s*["\']([^"\']+)["\']', args_str)
                    if content_match:
                        args["content"] = content_match.group(1)
                
                if args:
                    tool_calls.append({
                        "tool": tool_name,
                        "arguments": args
                    })
            except Exception:
                # Skip malformed tool calls
                pass
        
        return tool_calls

    def _extract_actions(self, response_text: str) -> List[Dict[str, Any]]:
        """Extract actions from response text.
        
        Looks for JSON action format in response.
        
        Args:
            response_text: Response text from model
        
        Returns:
            List of action dicts
        """
        actions = []
        
        # Try to find JSON in response
        json_pattern = r'\{[^{}]*"actions"[^{}]*\[[^\]]*\][^{}]*\}'
        json_match = re.search(json_pattern, response_text, re.DOTALL)
        
        if json_match:
            try:
                parsed = json.loads(json_match.group(0))
                if isinstance(parsed, dict) and "actions" in parsed:
                    actions = parsed["actions"]
                    if isinstance(actions, list):
                        return actions
            except json.JSONDecodeError:
                pass
        
        # Fallback: look for action-like patterns
        # This is a simple heuristic - could be improved
        action_pattern = r'\{[^{}]*"kind"[^{}]*\}'
        action_matches = re.findall(action_pattern, response_text)
        
        for match in action_matches:
            try:
                action = json.loads(match)
                if isinstance(action, dict) and "kind" in action:
                    actions.append(action)
            except json.JSONDecodeError:
                pass
        
        return actions

    def _update_knowledge_base(self, response_text: str, kb_tool: Any) -> None:
        """Try to extract and update knowledge base from response.
        
        Looks for explicit knowledge base updates in response.
        
        Args:
            response_text: Response text from model
            kb_tool: Knowledge base tool instance
        """
        # Look for knowledge base update patterns
        kb_pattern = r'update_knowledge_base\([^)]+\)'
        kb_matches = re.findall(kb_pattern, response_text)
        
        for match in kb_matches:
            # Extract operation, section_id, content
            op_match = re.search(r'operation\s*=\s*["\']([^"\']+)["\']', match)
            sid_match = re.search(r'section_id\s*=\s*["\']([^"\']+)["\']', match)
            content_match = re.search(r'content\s*=\s*["\']([^"\']+)["\']', match)
            
            if op_match and sid_match and content_match:
                kb_tool.run({
                    "operation": op_match.group(1),
                    "section_id": sid_match.group(1),
                    "content": content_match.group(1)
                })

