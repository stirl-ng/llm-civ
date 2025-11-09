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


def load_schema(repo_root: Path, name: str) -> Dict[str, Any]:
    schema_path = repo_root / "schemas" / name
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate(obj: Dict[str, Any], schema: Dict[str, Any]) -> None:
    Draft202012Validator(schema).validate(obj)


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
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
    parser.add_argument("--config", required=True, help="Path to experiment YAML config")
    parser.add_argument("--dry-run", action="store_true", help="Run without orchestrator, just one step")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    cfg = load_config(Path(args.config))

    # Validate experiment config
    exp_schema = load_schema(repo_root, "experiment.schema.json")
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

