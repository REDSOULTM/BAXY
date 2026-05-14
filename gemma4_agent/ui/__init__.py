"""Gemma 4 Agent — Jarvis-style desktop GUI.

Entry point: python -m gemma4_agent.ui
Built on PyQt6. Aesthetic inspired by Mark XXXIX / Iron Man HUDs.

Single-process design: the GUI runs the agent in a worker QThread and wires
the agent's `progress` callback to Qt signals. No FastAPI / WebSocket — the
whole stack stays in one Python process.
"""
from __future__ import annotations

__all__ = ["main"]


def main() -> int:
    from .app import main as _main
    return _main()
