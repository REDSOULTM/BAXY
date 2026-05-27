"""App/window capability for computer-use."""
from __future__ import annotations

from .base import Capability


class AppCapability(Capability):
    ops = frozenset({"focus_app"})

    def run(self, op: str, arg: str, app_token: str) -> tuple[dict, str]:
        if op != "focus_app":
            return {"ok": False, "error": f"app capability cannot run {op}"}, app_token
        result = self.executor._focus_app(arg)
        full = str(result.get("focused") or "") or self.ag._window_title_in_text(arg) or arg
        return result, self.executor._app_token(full)
