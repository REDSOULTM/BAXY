"""Entry point invoked by Scheduled Tasks to evaluate a watcher.

Usage:
    python -m gemma4_agent.watcher_runner --id res_abc123

Loads the watcher from state, compares the current snapshot with the stored
snapshot, fires `on_change` (a tool+args dict) if there's a difference, and
updates the snapshot. Prints a one-line summary so the Scheduled Task log shows
what happened.
"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="gemma4_agent.watcher_runner")
    parser.add_argument("--id", required=True, help="watcher resource id (res_*)")
    args = parser.parse_args()

    from .config import AgentConfig
    from .memory import MemoryStore
    from .state import AgentState
    from .tools import ToolRegistry

    config = AgentConfig.from_env()
    memory = MemoryStore(config.memory_path)
    state = AgentState(config.state_path)
    registry = ToolRegistry(memory=memory, captures_dir=config.captures_dir, state=state, safety_enabled=False)

    result = registry.execute("watcher", {"action": "check", "id": args.id})
    if not result.get("ok"):
        print(f"watcher check failed: {result.get('error')}", file=sys.stderr)
        return 1
    changed = bool(result.get("changed"))
    triggered = result.get("triggered")
    print(f"watcher {args.id} changed={changed} triggered={bool(triggered)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
