"""Discord/chat capability for computer-use.

The public planner still emits primitives. This capability owns Discord/chat
specific primitives such as quick-switcher navigation and voice controls.
"""
from __future__ import annotations

from .base import Capability


class DiscordCapability(Capability):
    ops = frozenset({"open_chat", "open_voice", "discord_control"})

    def run(self, op: str, arg: str, app_token: str) -> tuple[dict, str]:
        win = app_token or "Discord"
        if op == "open_chat":
            return self.executor._open_chat(arg, win), win
        if op == "open_voice":
            return self.executor._open_voice(arg, win), win
        if op == "discord_control":
            return self.executor._discord_control(arg, win), win
        return {"ok": False, "error": f"discord capability cannot run {op}"}, app_token
