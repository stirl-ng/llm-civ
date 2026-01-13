from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict

import yaml
from jsonschema import Draft202012Validator

from agent_runtime import Agent, get_model, build_tools
from agent_runtime.strategies.vanilla import VanillaStrategy


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


def build_strategy(cfg: Dict[str, Any]):
    name = (cfg.get("name") or cfg.get("kind") or "vanilla").lower()
    if name == "vanilla":
        return VanillaStrategy(temperature=cfg.get("temperature", 0.2))
    raise ValueError(f"Unsupported strategy: {name}")


def dry_run(agent: Agent) -> None:
    # Minimal fake state to exercise the pipeline; real runs come from orchestrator
    state = {"turn": 1}
    actions = agent.step(state)
    print(json.dumps({"agent": agent.name(), "actions": actions}, indent=2))


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

    # Build components
    model = get_model(cfg.get("backend", {}))
    tools = build_tools(cfg.get("tools", []))
    strategy = build_strategy(cfg.get("strategy", {}))
    agent = Agent(model=model, tools=tools, strategy=strategy)

    if args.dry_run:
        dry_run(agent)
        return

    # Placeholders for orchestrator loop (pipe IO lives in python/orchestrator)
    pipe_name = cfg.get("orchestrator", {}).get("pipe", r"\\.\pipe\civv_llm")
    print(f"Configured to connect to pipe: {pipe_name}")
    print("For live runs, start python -m orchestrator and the game mod.")


if __name__ == "__main__":
    main()

