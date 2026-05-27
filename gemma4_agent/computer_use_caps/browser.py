"""Browser/navigation capability for computer-use.

The public primitive surface stays small. Internally, browser work gets a
structured path when a visible CDP session is already available, then falls back
to the existing UIA/keyboard path. We do not auto-restart the user's browser
from computer_use.
"""
from __future__ import annotations

import re
import time

from .base import Capability


_BROWSER_HINTS = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "edge",
    "microsoft edge": "edge",
    "msedge": "edge",
    "opera": "opera",
    "opera gx": "opera",
    "operagx": "opera",
    "brave": "brave",
    "brave browser": "brave",
}


def _fold(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").casefold()).strip()


def _normalize_url(url: str) -> str:
    u = (url or "").strip()
    if u and not re.match(r"^https?://", u, re.IGNORECASE):
        u = "https://" + u
    return u


class BrowserCapability(Capability):
    ops = frozenset({"open_url"})
    contextual_ops = frozenset({
        "click", "type", "fill_field", "toggle", "wait_for", "send", "keypress",
    })

    session_id = "computer_use"

    def __init__(self, executor):
        super().__init__(executor)
        self._cdp_attach_attempted: set[str] = set()
        self._cdp_available = False
        self._cdp_owns_active_tab = False
        self._cdp_unavailable_reason = ""

    def can_run_contextually(self, op: str, app_token: str) -> bool:
        return op in self.contextual_ops and self._browser_hint(app_token) is not None

    def run(self, op: str, arg: str, app_token: str) -> tuple[dict, str]:
        if op == "open_url":
            result = self._open_url(arg, app_token)
            next_token = app_token
            if not next_token:
                title = str(result.get("title") or "")
                if title:
                    next_token = self.executor._app_token(title)
            return result, next_token
        if op == "click" and self.can_run_contextually(op, app_token):
            return self._click(arg, app_token), app_token
        if op == "type" and self.can_run_contextually(op, app_token):
            return self._type(arg, app_token), app_token
        if op == "fill_field" and self.can_run_contextually(op, app_token):
            return self._fill_field(arg, app_token), app_token
        if op == "toggle" and self.can_run_contextually(op, app_token):
            return self._toggle(arg, app_token), app_token
        if op == "wait_for" and self.can_run_contextually(op, app_token):
            return self._wait_for(arg, app_token), app_token
        if op == "send" and self.can_run_contextually(op, app_token):
            return self._keypress("Enter", app_token), app_token
        if op == "keypress" and self.can_run_contextually(op, app_token):
            return self._keypress(arg, app_token), app_token
        return {"ok": False, "error": f"browser capability cannot run {op}"}, app_token

    def _browser_hint(self, app_token: str) -> str | None:
        """Return a browser adapter key for known browser products.

        This is adapter selection, not intent routing: the LLM already chose the
        closed primitive and the OS/app focus token is the input.
        """
        folded = _fold(app_token)
        if not folded:
            return None
        for token, adapter in _BROWSER_HINTS.items():
            if token in folded:
                return adapter
        return None

    def _try_attach_visible(self, app_token: str) -> bool:
        if self._cdp_available:
            return True
        browser = self._browser_hint(app_token)
        if not browser:
            return False
        if browser in self._cdp_attach_attempted:
            return False
        self._cdp_attach_attempted.add(browser)
        try:
            status = self.executor.tools.execute("browser_real", {"action": "status"})
            if not status.get("ok") or not status.get("available"):
                self._cdp_unavailable_reason = str(status.get("error") or "browser_real unavailable")
                return False
            attached = self.executor.tools.execute(
                "browser_real",
                {
                    "action": "attach_visible",
                    "session_id": self.session_id,
                    "browser": browser,
                    "port": 9222,
                },
            )
            if attached.get("ok"):
                self._cdp_available = True
                return True
            self._cdp_unavailable_reason = str(
                attached.get("error") or attached.get("completion_status") or "CDP attach failed"
            )
        except Exception as exc:  # noqa: BLE001 - never let structured path kill fallback
            self._cdp_unavailable_reason = str(exc)
        return False

    def _open_url(self, url: str, app_token: str) -> dict:
        u = _normalize_url(url)
        if self._try_attach_visible(app_token):
            try:
                r = self.executor.tools.execute(
                    "browser_real",
                    {
                        "action": "goto",
                        "session_id": self.session_id,
                        "url": u,
                        "headless": False,
                        "new_tab": True,
                        "wait_until": "domcontentloaded",
                        "timeout_sec": 20,
                    },
                )
                if r.get("ok"):
                    verified = bool(
                        r.get("verified") is True
                        or r.get("content_verified") is True
                        or (r.get("title") and r.get("url"))
                    )
                    self._cdp_owns_active_tab = True
                    return {
                        "ok": True,
                        "verified": verified,
                        "url": r.get("url") or u,
                        "title": r.get("title"),
                        "method": "browser_real_cdp",
                        "content_verified": bool(r.get("content_verified")),
                    }
                self._cdp_unavailable_reason = str(r.get("error") or "browser_real goto failed")
            except Exception as exc:  # noqa: BLE001
                self._cdp_unavailable_reason = str(exc)
        fallback = self.executor._open_url(u, app_token)
        if self._cdp_unavailable_reason:
            fallback.setdefault("structured_browser_unavailable", self._cdp_unavailable_reason)
        return fallback

    @staticmethod
    def _playwright_key(keys: str) -> str:
        parts = [p.strip() for p in re.split(r"[+ ]+", keys or "") if p.strip()]
        if not parts:
            return "Enter"
        aliases = {
            "ctrl": "Control",
            "control": "Control",
            "alt": "Alt",
            "shift": "Shift",
            "enter": "Enter",
            "esc": "Escape",
            "escape": "Escape",
            "space": "Space",
            "tab": "Tab",
            "backspace": "Backspace",
            "delete": "Delete",
        }
        mapped = [aliases.get(p.casefold(), p[:1].upper() + p[1:] if len(p) > 1 else p.upper()) for p in parts]
        return "+".join(mapped)

    def _click(self, label: str, app_token: str) -> dict:
        # Only use DOM/CDP clicks on a tab this capability opened. When the user
        # asked to click browser chrome (bookmarks/favorites bar), DOM cannot see
        # it and UIA is the correct grounding layer.
        if self._cdp_available and self._cdp_owns_active_tab:
            try:
                r = self.executor.tools.execute(
                    "browser_real",
                    {
                        "action": "click_accessible",
                        "session_id": self.session_id,
                        "name": label,
                        "target": label,
                        "timeout_sec": 8,
                    },
                )
                if r.get("ok"):
                    return {
                        "ok": True,
                        "verified": bool(r.get("verified")),
                        "label": label,
                        "method": "browser_real_accessible",
                        "state_changed": r.get("state_changed"),
                        "completion_status": r.get("completion_status"),
                    }
                # Not found in DOM likely means browser chrome/bookmark or a
                # non-webview surface; fall through to UIA click_button.
                self._cdp_unavailable_reason = str(r.get("error") or "accessible click failed")
            except Exception as exc:  # noqa: BLE001
                self._cdp_unavailable_reason = str(exc)
        fallback = self.executor._click(label, app_token)
        if self._cdp_unavailable_reason:
            fallback.setdefault("structured_browser_unavailable", self._cdp_unavailable_reason)
        return fallback

    def _type(self, text: str, app_token: str) -> dict:
        if self._cdp_available and self._cdp_owns_active_tab:
            try:
                r = self.executor.tools.execute(
                    "browser_real",
                    {
                        "action": "type_text",
                        "session_id": self.session_id,
                        "value": text,
                        "timeout_sec": 5,
                    },
                )
                if r.get("ok"):
                    return {
                        "ok": True,
                        "verified": bool(r.get("verified")),
                        "text": text,
                        "method": "browser_real_keyboard",
                        "state_changed": r.get("state_changed"),
                        "completion_status": r.get("completion_status"),
                    }
                self._cdp_unavailable_reason = str(r.get("error") or "browser_real type failed")
            except Exception as exc:  # noqa: BLE001
                self._cdp_unavailable_reason = str(exc)
        fallback = self.executor._type(text, app_token)
        if self._cdp_unavailable_reason:
            fallback.setdefault("structured_browser_unavailable", self._cdp_unavailable_reason)
        return fallback

    def _fill_field(self, spec: str, app_token: str) -> dict:
        parsed = self.executor._split_field_value(spec)
        if parsed is None:
            return self.executor._fill_field(spec, app_token)
        field, value = parsed
        if self._cdp_available and self._cdp_owns_active_tab:
            try:
                clicked = self.executor.tools.execute(
                    "browser_real",
                    {
                        "action": "click_accessible",
                        "session_id": self.session_id,
                        "name": field,
                        "target": field,
                        "timeout_sec": 8,
                    },
                )
                if clicked.get("ok"):
                    typed = self.executor.tools.execute(
                        "browser_real",
                        {
                            "action": "type_text",
                            "session_id": self.session_id,
                            "value": value,
                            "timeout_sec": 5,
                        },
                    )
                    return {
                        "ok": bool(typed.get("ok")),
                        "verified": typed.get("verified") is True,
                        "field": field,
                        "value_chars": len(value),
                        "method": "browser_real_accessible_type",
                        "click": clicked,
                        "type": typed,
                    }
                self._cdp_unavailable_reason = str(clicked.get("error") or "accessible field click failed")
            except Exception as exc:  # noqa: BLE001
                self._cdp_unavailable_reason = str(exc)
        fallback = self.executor._fill_field(spec, app_token)
        if self._cdp_unavailable_reason:
            fallback.setdefault("structured_browser_unavailable", self._cdp_unavailable_reason)
        return fallback

    def _toggle(self, spec: str, app_token: str) -> dict:
        label, desired = self.executor._parse_toggle_spec(spec)
        if not label:
            return {"ok": False, "verified": False, "error": "toggle requires label or label=on/off"}
        if self._cdp_available and self._cdp_owns_active_tab:
            try:
                r = self.executor.tools.execute(
                    "browser_real",
                    {
                        "action": "toggle_accessible",
                        "session_id": self.session_id,
                        "name": label,
                        "target": label,
                        "desired": desired,
                        "timeout_sec": 5,
                    },
                )
                if r.get("ok"):
                    return {
                        "ok": True,
                        "verified": r.get("verified") is True,
                        "label": label,
                        "desired": desired,
                        "method": "browser_real_dom_toggle",
                        "state": r.get("state"),
                        "completion_status": r.get("completion_status"),
                    }
                reason = r.get("error") or r.get("reason")
                self._cdp_unavailable_reason = str(reason or "browser_real toggle failed")
            except Exception as exc:  # noqa: BLE001
                self._cdp_unavailable_reason = str(exc)
        fallback = self.executor._toggle(spec, app_token)
        if self._cdp_unavailable_reason:
            fallback.setdefault("structured_browser_unavailable", self._cdp_unavailable_reason)
        return fallback

    def _wait_for(self, target: str, app_token: str) -> dict:
        label = (target or "").strip()
        if not label:
            return {"ok": False, "verified": False, "error": "wait_for requires target text"}
        if self._cdp_available and self._cdp_owns_active_tab:
            deadline = time.monotonic() + 12.0
            last: dict | None = None
            while time.monotonic() < deadline:
                try:
                    r = self.executor.tools.execute(
                        "browser_real",
                        {
                            "action": "text",
                            "session_id": self.session_id,
                            "max_chars": 12000,
                            "timeout_sec": 5,
                        },
                    )
                    last = r if isinstance(r, dict) else {"ok": False}
                    text = str((r or {}).get("text") or "")
                    if r.get("ok") and label.casefold() in text.casefold():
                        return {
                            "ok": True,
                            "verified": True,
                            "target": label,
                            "method": "browser_real_text",
                            "content_verified": True,
                        }
                except Exception as exc:  # noqa: BLE001
                    last = {"ok": False, "error": str(exc)}
                time.sleep(0.5)
            return {
                "ok": False,
                "verified": False,
                "target": label,
                "method": "browser_real_text",
                "error": "target_not_found_before_timeout",
                "last": last,
            }
        fallback = self.executor._wait_for(label, app_token)
        if self._cdp_unavailable_reason:
            fallback.setdefault("structured_browser_unavailable", self._cdp_unavailable_reason)
        return fallback

    def _keypress(self, keys: str, app_token: str) -> dict:
        if self._cdp_available and self._cdp_owns_active_tab:
            try:
                key = self._playwright_key(keys)
                r = self.executor.tools.execute(
                    "browser_real",
                    {
                        "action": "press",
                        "session_id": self.session_id,
                        "key": key,
                        "timeout_sec": 5,
                    },
                )
                if r.get("ok"):
                    return {
                        "ok": True,
                        "verified": r.get("verified") is True,
                        "keys": keys,
                        "method": "browser_real_press",
                    }
                self._cdp_unavailable_reason = str(r.get("error") or "browser_real press failed")
            except Exception as exc:  # noqa: BLE001
                self._cdp_unavailable_reason = str(exc)
        fallback = self.executor._keypress(keys, app_token)
        if self._cdp_unavailable_reason:
            fallback.setdefault("structured_browser_unavailable", self._cdp_unavailable_reason)
        return fallback
