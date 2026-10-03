"""Every pipe command in the DLL has a test. Needs no game."""

from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CVGAME = HERE.parents[1] / "Community-Patch-DLL" / "CvGameCoreDLL_Expansion2" / "CvGame.cpp"

# Commands covered elsewhere or deliberately not sent by the suite.
NOT_TESTED_HERE: dict[str, str] = {}


def dll_commands() -> set[str]:
    source = CVGAME.read_text(encoding="latin-1")
    body = source[source.index("void CvGame::HandlePipeCommand"):]
    return set(re.findall(r'msgType == "([a-z_]+)"', body))


def commands_in_tests() -> set[str]:
    text = "\n".join(p.read_text(encoding="utf-8") for p in HERE.glob("test_*.py") if p.name != Path(__file__).name)
    return set(re.findall(r'"([a-z_]+)"', text))


def test_every_dll_command_has_a_test():
    commands = dll_commands()
    assert len(commands) > 30, f"parsed only {len(commands)} commands from {CVGAME}; did the dispatch change?"
    missing = commands - commands_in_tests() - NOT_TESTED_HERE.keys()
    assert not missing, (
        f"DLL commands with no test in python/dlltest: {sorted(missing)}. "
        "Add a test, or list the command in NOT_TESTED_HERE with the reason."
    )
