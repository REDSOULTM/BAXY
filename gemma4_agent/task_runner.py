"""Unified entry point for Scheduled-Task invocations.

Replaces the two near-duplicate scripts routine_runner.py and
watcher_runner.py. Same dispatch shape (build a fresh ToolRegistry
without the LLM, call .execute(...) on the right tool, print a
one-line summary). The legacy scripts remain as thin wrappers so the
Scheduled Tasks already registered in Windows keep working unchanged.

Usage:
    python -m gemma4_agent.task_runner --type routine --label "My Routine"
    python -m gemma4_agent.task_runner --type routine --id res_abc123
    python -m gemma4_agent.task_runner --type watcher --id res_abc123
"""
from __future__ import annotations

import argparse
import sys
from typing import Sequence


def _build_registry():
    # Defer the heavy imports until we actually run (keeps argparse errors fast).
    from .config import AgentConfig
    from .memory import MemoryStore
    from .state import AgentState
    from .tools import ToolRegistry

    config = AgentConfig.from_env()
    memory = MemoryStore(config.memory_path)
    state = AgentState(config.state_path)
    return ToolRegistry(
        memory=memory,
        captures_dir=config.captures_dir,
        state=state,
        safety_enabled=False,
    )


def _run_routine(args: argparse.Namespace) -> int:
    if not args.id and not args.label:
        print("error: --id or --label required for --type routine", file=sys.stderr)
        return 2
    registry = _build_registry()
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


def _run_watcher(args: argparse.Namespace) -> int:
    if not args.id:
        print("error: --id required for --type watcher", file=sys.stderr)
        return 2
    registry = _build_registry()
    result = registry.execute("watcher", {"action": "check", "id": args.id})
    if not result.get("ok"):
        print(f"watcher check failed: {result.get('error')}", file=sys.stderr)
        return 1
    changed = bool(result.get("changed"))
    triggered = result.get("triggered")
    print(f"watcher {args.id} changed={changed} triggered={bool(triggered)}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gemma4_agent.task_runner")
    parser.add_argument(
        "--type",
        required=True,
        choices=["routine", "watcher"],
        help="which scheduled-task kind this invocation is for",
    )
    parser.add_argument("--id", help="resource id (res_*) — required for watcher")
    parser.add_argument("--label", help="routine label/name (routine only)")
    args = parser.parse_args(argv)

    if args.type == "routine":
        return _run_routine(args)
    return _run_watcher(args)


if __name__ == "__main__":
    raise SystemExit(main())
