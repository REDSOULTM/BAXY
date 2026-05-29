"""Backwards-compatible thin wrapper around :mod:`gemma4_agent.task_runner`.

The Scheduled Tasks already registered in Windows invoke this module
by name (``python -m gemma4_agent.infra.watcher_runner ...``). Implementation
moved to :mod:`gemma4_agent.task_runner` to share code with the routine
runner; this file forwards the call.
"""
from __future__ import annotations

import sys

from .task_runner import main as _main


def main() -> int:
    return _main(["--type", "watcher", *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
