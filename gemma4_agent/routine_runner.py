"""Entry point invoked by Scheduled Tasks to execute a routine's steps.

Usage:
    python -m gemma4_agent.routine_runner --label "My Routine"
    python -m gemma4_agent.routine_runner --id res_abc123

The runner loads the routine from state.json, builds a fresh ToolRegistry
without the LLM, and executes every step. The run is appended to the
routine's history in state.json so that `routine(action="history")` can
report it back.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(prog="gemma4_agent.routine_runner")
    parser.add_argument("--id", help="routine resource id (res_*)")
    parser.add_argument("--label", help="routine label/name")
    args = parser.parse_args()

    if not args.id and not args.label:
        print("error: --id or --label required", file=sys.stderr)
        return 2

    # Defer imports to keep startup cheap and avoid side effects until needed.
    from .config import AgentConfig
    from .memory import MemoryStore
    from .state import AgentState
    from .tools import ToolRegistry

    config = AgentConfig.from_env()
    memory = MemoryStore(config.memory_path)
    state = AgentState(config.state_path)
    registry = ToolRegistry(memory=memory, captures_dir=config.captures_dir, state=state, safety_enabled=False)

    routine_args: dict = {"action": "run_now"}
    if args.id:
        routine_args["id"] = args.id
    if args.label:
        routine_args["name"] = args.label

    result = registry.execute("routine", routine_args)
    if not result.get("ok"):
        print(f"routine run failed: {result.get('error')}", file=sys.stderr)
        return 1
    print(f"routine ran: completed={result.get('completed')} steps={len(result.get('results', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
