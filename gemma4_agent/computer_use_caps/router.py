"""Dispatcher for internal computer-use capabilities."""
from __future__ import annotations

from typing import Any

from .apps import AppCapability
from .browser import BrowserCapability
from .discord import DiscordCapability
from .generic_ui import GenericUICapability


class CapabilityRouter:
    """Route closed-vocabulary primitives to domain capabilities.

    This keeps the public tool compound-style (``computer_use(goal=...)``) while
    making the inside look like the rest of the system: small domain executors
    with focused tests.
    """

    hard_fail_ops = frozenset({
        "focus_app",
        "open_chat",
        "open_voice",
        "open_url",
        "type",
        "click",
        "fill_field",
        "toggle",
        "wait_for",
        "discord_control",
    })
    verified_ops = hard_fail_ops | frozenset({
        "send",
        "keypress",
        "scroll",
        "wait",
    })

    def __init__(self, executor: Any):
        self.apps = AppCapability(executor)
        self.discord = DiscordCapability(executor)
        self.browser = BrowserCapability(executor)
        self.generic_ui = GenericUICapability(executor)
        self._by_op = {}
        for capability in (self.apps, self.discord, self.browser, self.generic_ui):
            for op in capability.ops:
                self._by_op[op] = capability

    @staticmethod
    def _snapshot_browser_token(snapshot: dict | None) -> str:
        if not isinstance(snapshot, dict) or not snapshot.get("is_browser"):
            return ""
        return str(
            snapshot.get("window_title")
            or snapshot.get("process_name")
            or snapshot.get("window_class")
            or ""
        )

    def run(
        self,
        op: str,
        arg: str,
        app_token: str,
        snapshot: dict | None = None,
        policy: dict | None = None,
    ) -> tuple[dict, str]:
        primary = str((policy or {}).get("primary") or "")
        if primary.startswith("browser_") and op in (self.browser.contextual_ops | self.browser.ops):
            browser_token = app_token or self._snapshot_browser_token(snapshot)
            if browser_token:
                return self.browser.run(op, arg, browser_token)
        if self.browser.can_run_contextually(op, app_token):
            return self.browser.run(op, arg, app_token)
        capability = self._by_op.get(op)
        if capability is None:
            return {"ok": False, "error": f"primitiva desconocida: {op}"}, app_token
        return capability.run(op, arg, app_token)

    def is_hard_fail(self, op: str) -> bool:
        return op in self.hard_fail_ops

    def is_verified_step(self, op: str) -> bool:
        return op in self.verified_ops
