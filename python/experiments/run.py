from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import yaml
from jsonschema import Draft202012Validator

from agent_runtime import Agent, get_model, build_tools
from agent_runtime.memory import KnowledgeBase
from agent_runtime.strategies.vanilla import VanillaStrategy
from agent_runtime.strategies.enhanced import EnhancedStrategy
from agent_runtime.tools.knowledge_base_tool import KnowledgeBaseTool


def load_schema(python_root: Path, name: str) -> Dict[str, Any]:
    schema_path = python_root / "schemas" / name
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate(obj: Dict[str, Any], schema: Dict[str, Any]) -> None:
    Draft202012Validator(schema).validate(obj)


def load_config(config_arg: str) -> Dict[str, Any]:
    """
    Load config from a path or short name.
    
    If config_arg is a short name (no path separators), looks for it in
    python/configs/experiments/{name}.yaml. Otherwise treats it as a file path.
    """
    config_path = Path(config_arg)
    
    # If it's not an absolute path and has no path separators, treat as short name
    if not config_path.is_absolute() and "/" not in config_arg and "\\" not in config_arg:
        # Resolve relative to python/configs/experiments/
        python_root = Path(__file__).resolve().parent.parent
        config_path = python_root / "configs" / "experiments" / f"{config_arg}.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_strategy(cfg: Dict[str, Any], knowledge_base: KnowledgeBase = None):
    name = (cfg.get("name") or cfg.get("kind") or "enhanced").lower()
    if name == "vanilla":
        return VanillaStrategy(temperature=cfg.get("temperature", 0.2))
    elif name == "enhanced":
        return EnhancedStrategy(
            knowledge_base=knowledge_base,
            temperature=cfg.get("temperature", 0.2)
        )
    raise ValueError(f"Unsupported strategy: {name}")


def dry_run(agent: Agent) -> None:
    # Minimal fake state to exercise the pipeline; real runs come from orchestrator
    state = {"turn": 1}
    actions = agent.step(state)
    print(json.dumps({"agent": agent.name(), "actions": actions}, indent=2))


def call_orchestrator_tool(base_url: str, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Call an orchestrator tool via HTTP."""
    try:
        response = requests.post(
            f"{base_url}/tool",
            json={"tool": tool, "arguments": arguments},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to call orchestrator tool {tool}: {e}") from e


def check_orchestrator_health(base_url: str) -> bool:
    """Check if orchestrator is running."""
    try:
        response = requests.get(f"{base_url}/health", timeout=5.0)
        response.raise_for_status()
        return response.json().get("status") == "ok"
    except requests.exceptions.RequestException:
        return False


def get_game_status(base_url: str) -> Optional[Dict[str, Any]]:
    """Get current turn status from orchestrator (non-logging endpoint)."""
    try:
        response = requests.get(f"{base_url}/status", timeout=5.0)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException:
        return None


def send_actions_to_orchestrator(base_url: str, actions: list, notes: str = "") -> Dict[str, Any]:
    """Send actions to orchestrator."""
    if not actions:
        return {"status": "success", "message": "No actions to send"}
    
    # Use send_actions if available, otherwise send individually
    try:
        result = call_orchestrator_tool(base_url, "send_actions", {
            "actions": actions,
            "notes": notes
        })
        return result
    except RuntimeError:
        # Fallback to individual send_action calls
        results = []
        for action in actions:
            try:
                result = call_orchestrator_tool(base_url, "send_action", {
                    "action": action,
                    "notes": notes if len(actions) == 1 else ""
                })
                results.append(result)
            except Exception as e:
                results.append({"status": "error", "error": str(e)})
        return {"status": "success", "results": results}


def end_turn(base_url: str, turn: int) -> Dict[str, Any]:
    """End the current turn."""
    return call_orchestrator_tool(base_url, "end_turn", {"turn": turn})


def run_game_loop(agent: Agent, base_url: str, poll_interval: float = 2.0, turn_timeout: float = 300.0) -> None:
    """Main game loop that polls for turns and processes them.
    
    Args:
        agent: The agent to run
        base_url: Orchestrator base URL
        poll_interval: Seconds between status polls
        turn_timeout: Maximum seconds per turn (default 5 minutes)
    """
    print(f"Connecting to orchestrator at {base_url}...")
    
    # Wait for orchestrator to be available
    max_wait = 30
    waited = 0
    while not check_orchestrator_health(base_url):
        if waited >= max_wait:
            raise RuntimeError(f"Orchestrator not available at {base_url} after {max_wait} seconds")
        print(f"Waiting for orchestrator... ({waited}/{max_wait}s)")
        time.sleep(1.0)
        waited += 1
    
    print("Orchestrator connected!")
    print(f"Agent: {agent.name()}")
    print(f"Turn timeout: {turn_timeout}s")
    print("Waiting for game to start...")
    
    last_turn: Optional[int] = None
    game_over = False
    
    # Turn and action statistics
    turn_stats: Dict[int, Dict[str, Any]] = {}
    total_actions = 0
    total_action_errors = 0
    
    try:
        while not game_over:
            # Check turn status (non-logging endpoint, doesn't spam logs)
            status = get_game_status(base_url)
            
            if status is None or not status.get("connected"):
                # No connection yet, wait and retry
                time.sleep(poll_interval)
                continue
            
            # Extract turn number
            current_turn = status.get("turn")
            
            # Check if this is a new turn
            if current_turn is None:
                # Game not started yet
                time.sleep(poll_interval)
                continue
            
            if last_turn is not None and current_turn == last_turn:
                # Same turn, wait for next turn
                time.sleep(poll_interval)
                continue
            
            # New turn detected!
            turn_start_time = time.time()
            print(f"\n{'='*60}")
            print(f"Turn {current_turn} started")
            print(f"{'='*60}")
            
            last_turn = current_turn
            
            # Initialize turn statistics
            turn_action_count = 0
            turn_action_errors = 0
            
            # Process the turn
            try:
                # Get agent's actions for this turn
                # The LLM will get state via tools when it needs it
                print("Getting agent decisions...")
                # Pass minimal state - LLM will query what it needs
                minimal_state = {"turn": current_turn}
                agent_start_time = time.time()
                action_result = agent.step(minimal_state)
                agent_time = time.time() - agent_start_time
                
                # Extract actions from result
                actions = action_result.get("actions", [])
                notes = action_result.get("notes", "")
                
                if notes:
                    print(f"Agent notes: {notes}")
                
                # Send actions if any
                if actions:
                    if not isinstance(actions, list):
                        actions = [actions]
                    
                    turn_action_count = len(actions)
                    total_actions += turn_action_count
                    
                    print(f"Sending {turn_action_count} action(s)...")
                    send_result = send_actions_to_orchestrator(base_url, actions, notes)
                    
                    if send_result.get("status") == "error":
                        turn_action_errors += 1
                        total_action_errors += 1
                        print(f"Warning: Error sending actions: {send_result.get('error', 'Unknown error')}")
                    else:
                        # Check for individual action errors in results
                        results = send_result.get("results", [])
                        for result in results:
                            if result.get("status") == "error":
                                turn_action_errors += 1
                                total_action_errors += 1
                        print("Actions sent successfully")
                else:
                    print("No actions to send")
                
                # End the turn
                print(f"Ending turn {current_turn}...")
                end_result = end_turn(base_url, current_turn)
                
                if end_result.get("status") == "error":
                    error_msg = end_result.get("error", "Unknown error")
                    print(f"Warning: Error ending turn: {error_msg}")
                    # Check if it's a game over condition
                    if "game" in error_msg.lower() and "over" in error_msg.lower():
                        game_over = True
                else:
                    print(f"Turn {current_turn} ended successfully")
                
                # Calculate turn timing
                turn_end_time = time.time()
                turn_duration = turn_end_time - turn_start_time
                
                # Store turn statistics
                turn_stats[current_turn] = {
                    "turn": current_turn,
                    "duration": turn_duration,
                    "agent_time": agent_time,
                    "action_count": turn_action_count,
                    "action_errors": turn_action_errors,
                    "timed_out": turn_duration >= turn_timeout,
                }
                
                # Print turn summary
                print(f"\nTurn {current_turn} summary:")
                print(f"  Duration: {turn_duration:.2f}s")
                print(f"  Agent time: {agent_time:.2f}s")
                print(f"  Actions: {turn_action_count} ({turn_action_errors} errors)")
                if turn_duration >= turn_timeout:
                    print(f"  ⚠️  TURN TIMEOUT ({turn_duration:.2f}s >= {turn_timeout}s)")
                print()
                
            except KeyboardInterrupt:
                print("\nInterrupted by user")
                game_over = True
            except Exception as e:
                print(f"Error processing turn: {e}")
                # Record failed turn
                turn_end_time = time.time()
                turn_duration = turn_end_time - turn_start_time
                turn_stats[current_turn] = {
                    "turn": current_turn,
                    "duration": turn_duration,
                    "agent_time": None,
                    "action_count": turn_action_count,
                    "action_errors": turn_action_errors,
                    "timed_out": turn_duration >= turn_timeout,
                    "error": str(e),
                }
                # Continue loop, but log the error
                import traceback
                traceback.print_exc()
                time.sleep(poll_interval)
            
            # Small delay before next poll
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\nGame loop interrupted by user")
    except Exception as e:
        print(f"Fatal error in game loop: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    # Print final statistics
    print("\n" + "="*60)
    print("EXPERIMENT STATISTICS")
    print("="*60)
    
    if turn_stats:
        total_turns = len(turn_stats)
        total_duration = sum(s["duration"] for s in turn_stats.values())
        avg_duration = total_duration / total_turns if total_turns > 0 else 0
        max_duration = max(s["duration"] for s in turn_stats.values())
        min_duration = min(s["duration"] for s in turn_stats.values())
        
        timed_out_turns = sum(1 for s in turn_stats.values() if s.get("timed_out", False))
        
        print(f"Total turns: {total_turns}")
        print(f"Total duration: {total_duration:.2f}s ({total_duration/60:.2f} minutes)")
        print(f"Average turn duration: {avg_duration:.2f}s")
        print(f"Min turn duration: {min_duration:.2f}s")
        print(f"Max turn duration: {max_duration:.2f}s")
        print(f"Turn timeouts: {timed_out_turns}")
        print()
        print(f"Total actions: {total_actions}")
        print(f"Total action errors: {total_action_errors}")
        if total_actions > 0:
            error_rate = (total_action_errors / total_actions) * 100
            print(f"Action error rate: {error_rate:.2f}%")
        print()
        
        # Show slowest turns
        if total_turns > 0:
            sorted_turns = sorted(turn_stats.items(), key=lambda x: x[1]["duration"], reverse=True)
            print("Slowest 5 turns:")
            for turn_num, stats in sorted_turns[:5]:
                print(f"  Turn {turn_num}: {stats['duration']:.2f}s "
                      f"({stats['action_count']} actions, {stats['action_errors']} errors)")
    else:
        print("No turns processed")
    
    print("="*60)
    print("Game loop ended")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Civ V LLM experiments")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to experiment YAML config or short name (e.g., 'gemini' for python/configs/experiments/gemini.yaml)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run without orchestrator, just one step")
    args = parser.parse_args()

    python_root = Path(__file__).resolve().parent.parent
    cfg = load_config(args.config)

    # Validate experiment config
    exp_schema = load_schema(python_root, "experiment.schema.json")
    validate(cfg, exp_schema)

    # Get orchestrator configuration (needed for tools)
    orchestrator_cfg = cfg.get("orchestrator", {})
    base_url = orchestrator_cfg.get("url", "http://localhost:8765")
    
    # Initialize knowledge base
    knowledge_base = KnowledgeBase()
    
    # Build components
    model = get_model(cfg.get("backend", {}))
    tools = build_tools(cfg.get("tools", []), base_url=base_url)
    
    # Add knowledge base tool
    kb_tool = KnowledgeBaseTool(knowledge_base)
    tools.append(kb_tool)
    
    strategy = build_strategy(cfg.get("strategy", {}), knowledge_base=knowledge_base)
    agent = Agent(model=model, tools=tools, strategy=strategy)

    if args.dry_run:
        dry_run(agent)
        return

    # Get orchestrator configuration (base_url already retrieved above)
    orchestrator_cfg = cfg.get("orchestrator", {})
    pipe_name = orchestrator_cfg.get("pipe", r"\\.\pipe\civv_llm")
    poll_interval = orchestrator_cfg.get("poll_interval", 2.0)
    turn_timeout = orchestrator_cfg.get("turn_timeout", 300.0)
    
    print(f"Orchestrator pipe: {pipe_name}")
    print(f"Orchestrator URL: {base_url}")
    print(f"Poll interval: {poll_interval}s")
    print(f"Turn timeout: {turn_timeout}s")
    print()
    
    # Run the game loop
    run_game_loop(agent, base_url, poll_interval, turn_timeout)


if __name__ == "__main__":
    main()

