#!/usr/bin/env python3
"""Launch orchestrator + agent runners in a tmux session.

Usage:
  python launch.py                  # interactive config selection
  python launch.py gemini           # single runner, no prompt
  python launch.py gemini openai    # two runners
"""
import subprocess
import sys
from pathlib import Path

CONFIGS_DIR = Path(__file__).parent / "configs" / "experiments"
SESSION = "civ"


def available_configs() -> list[str]:
    return sorted(p.stem for p in CONFIGS_DIR.glob("*.yaml"))


def pick_configs() -> list[str]:
    configs = available_configs()
    print("Available configs:")
    for i, name in enumerate(configs, 1):
        print(f"  {i}) {name}")
    raw = input("Select (numbers or names, space-separated): ").strip().split()

    selected = []
    for token in raw:
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(configs):
                selected.append(configs[idx])
            else:
                print(f"  Skipping invalid index: {token}")
        elif token in configs:
            selected.append(token)
        else:
            print(f"  Unknown config: {token}")
    return selected


def tmux(args: list[str]) -> None:
    subprocess.run(["tmux"] + args, check=True)


def session_exists() -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", SESSION],
        capture_output=True,
    )
    return result.returncode == 0


def launch(configs: list[str]) -> None:
    if session_exists():
        print(f"tmux session '{SESSION}' already exists — kill it first with: tmux kill-session -t {SESSION}")
        sys.exit(1)

    orch_cmd = "python -m orchestrator"
    runner_cmd = lambda cfg: f"python -m agent_runtime --config {cfg}"

    # First pane: orchestrator
    tmux(["new-session", "-d", "-s", SESSION, "-n", "orch", "-x", "220", "-y", "50"])
    tmux(["send-keys", "-t", f"{SESSION}:orch", orch_cmd, "Enter"])

    # Remaining panes: one per runner
    for cfg in configs:
        tmux(["split-window", "-h", "-t", f"{SESSION}:orch"])
        tmux(["send-keys", "-t", f"{SESSION}:orch", runner_cmd(cfg), "Enter"])

    tmux(["select-layout", "-t", f"{SESSION}:orch", "even-horizontal"])
    tmux(["attach-session", "-t", SESSION])


def main() -> None:
    configs = sys.argv[1:] or pick_configs()
    if not configs:
        print("No configs selected.")
        sys.exit(1)

    unknown = [c for c in configs if c not in available_configs()]
    if unknown:
        print(f"Unknown configs: {', '.join(unknown)}")
        sys.exit(1)

    print(f"Launching: orchestrator + {configs}")
    launch(configs)


if __name__ == "__main__":
    main()
