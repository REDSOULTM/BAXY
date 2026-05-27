"""Generic UI/input capability for computer-use."""
from __future__ import annotations

from .base import Capability


class GenericUICapability(Capability):
    ops = frozenset({
        "type", "send", "keypress", "click", "fill_field", "toggle", "wait_for",
        "scroll", "wait",
    })

    def run(self, op: str, arg: str, app_token: str) -> tuple[dict, str]:
        if op == "type":
            return self.executor._type(arg, app_token), app_token
        if op == "send":
            return self.executor._send(app_token), app_token
        if op == "keypress":
            return self.executor._keypress(arg, app_token), app_token
        if op == "click":
            return self.executor._click(arg, app_token), app_token
        if op == "fill_field":
            return self.executor._fill_field(arg, app_token), app_token
        if op == "toggle":
            return self.executor._toggle(arg, app_token), app_token
        if op == "wait_for":
            return self.executor._wait_for(arg, app_token), app_token
        if op == "scroll":
            return self.executor._scroll(arg, app_token), app_token
        if op == "wait":
            return self.executor._wait(arg), app_token
        return {"ok": False, "error": f"generic UI capability cannot run {op}"}, app_token
