"""Mock-only tests for browser_real accessible actions.

These tests never launch Playwright or a real browser; they inject a fake page
into the browser session registry.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from gemma4_agent.tools_pkg import ops_tools



class _FakeFirst:
    def __init__(self, page, *, changes: bool = True):
        self.page = page
        self.changes = changes
        self.clicked = False

    def click(self, timeout=0):
        self.clicked = True
        if self.changes:
            self.page.url = "https://example.com/after"
            self.page.text = "after state"


class _FakeLocator:
    def __init__(self, page, *, changes: bool = True):
        self.first = _FakeFirst(page, changes=changes)


class _FakeContext:
    def __init__(self, page):
        self.pages = [page]


class _FakeKeyboard:
    def __init__(self, page):
        self.page = page

    def type(self, text):
        self.page.active_value += text
        self.page.text = f"body {self.page.active_value}"


class _FakePage:
    def __init__(self, *, changes: bool = True, password: bool = False):
        self.url = "https://example.com/before"
        self.text = "before state"
        self.context = _FakeContext(self)
        self.keyboard = _FakeKeyboard(self)
        self._changes = changes
        self._password = password
        self.active_value = ""

    def is_closed(self):
        return False

    def inner_text(self, selector, timeout=0):
        return self.text

    def get_by_role(self, role, name=None, exact=False):
        if role == "button" and name == "Continue":
            return _FakeLocator(self, changes=self._changes)
        raise RuntimeError("role not found")

    def get_by_label(self, target, exact=False):
        if target == "Email":
            return _FakeLocator(self, changes=self._changes)
        raise RuntimeError("label not found")

    def get_by_placeholder(self, target, exact=False):
        raise RuntimeError("placeholder not found")

    def get_by_title(self, target, exact=False):
        raise RuntimeError("title not found")

    def get_by_alt_text(self, target, exact=False):
        raise RuntimeError("alt not found")

    def get_by_text(self, target, exact=False):
        if target == "Continue":
            return _FakeLocator(self, changes=self._changes)
        raise RuntimeError("text not found")

    def wait_for_load_state(self, state, timeout=0):
        return None

    def evaluate(self, script):
        kind = "password" if self._password else "text"
        text_hash = "" if self._password else f"{len(self.active_value)}:{self.active_value[-64:]}"
        return {
            "tag": "input",
            "type": kind,
            "editable": False,
            "textHash": text_hash,
            "textLen": 0 if self._password else len(self.active_value),
        }


class BrowserRealAccessibleTest(unittest.TestCase):
    def setUp(self):
        self._sessions = dict(ops_tools._BROWSER_SESSIONS)
        ops_tools._BROWSER_SESSIONS.clear()

    def tearDown(self):
        ops_tools._BROWSER_SESSIONS.clear()
        ops_tools._BROWSER_SESSIONS.update(self._sessions)

    def _run(self, page):
        ops_tools._BROWSER_SESSIONS["sid"] = {
            "pages": [page], "active": 0, "context": page.context,
        }
        with tempfile.TemporaryDirectory() as td:
            return ops_tools.browser_real_tool(
                {"action": "click_accessible", "session_id": "sid", "name": "Continue"},
                MagicMock(),
                Path(td),
            )

    def test_click_accessible_verifies_state_change(self):
        result = self._run(_FakePage(changes=True))
        self.assertTrue(result["ok"])
        self.assertTrue(result["verified"])
        self.assertTrue(result["state_changed"])
        self.assertIn("role:button", result["attempts"])

    def test_click_accessible_does_not_claim_verified_without_change(self):
        result = self._run(_FakePage(changes=False))
        self.assertTrue(result["ok"])
        self.assertFalse(result["verified"])
        self.assertFalse(result["state_changed"])
        self.assertEqual(result["completion_status"], "clicked_accessible_unverified")

    def test_click_accessible_uses_label_fallback(self):
        page = _FakePage(changes=True)
        ops_tools._BROWSER_SESSIONS["sid"] = {
            "pages": [page], "active": 0, "context": page.context,
        }
        with tempfile.TemporaryDirectory() as td:
            result = ops_tools.browser_real_tool(
                {"action": "click_accessible", "session_id": "sid", "name": "Email"},
                MagicMock(),
                Path(td),
            )
        self.assertTrue(result["ok"])
        self.assertIn("label", result["attempts"])

    def test_type_text_verifies_active_element_change(self):
        page = _FakePage()
        ops_tools._BROWSER_SESSIONS["sid"] = {
            "pages": [page], "active": 0, "context": page.context,
        }
        with tempfile.TemporaryDirectory() as td:
            result = ops_tools.browser_real_tool(
                {"action": "type_text", "session_id": "sid", "text": "hello"},
                MagicMock(),
                Path(td),
            )
        self.assertTrue(result["ok"])
        self.assertTrue(result["verified"])
        self.assertEqual(result["typed_chars"], 5)

    def test_type_text_refuses_password_field(self):
        page = _FakePage(password=True)
        ops_tools._BROWSER_SESSIONS["sid"] = {
            "pages": [page], "active": 0, "context": page.context,
        }
        with tempfile.TemporaryDirectory() as td:
            result = ops_tools.browser_real_tool(
                {"action": "type_text", "session_id": "sid", "text": "secret"},
                MagicMock(),
                Path(td),
            )
        self.assertFalse(result["ok"])
        self.assertEqual(result["completion_status"], "needs_secret_handoff")


class AttachVisibleAutoLaunchTest(unittest.TestCase):
    """attach_visible debe AUTO-LANZAR una instancia CDP dedicada cuando ningún
    navegador escucha el puerto (el código garantiza su
    precondición). Todo mockeado: nunca lanza un navegador real."""

    def test_auto_launches_dedicated_instance_when_no_endpoint(self):
        # endpoint muerto al inicio -> debe llamar al launcher, no devolver needs_user.
        with patch.object(ops_tools, "_cdp_endpoint_alive", return_value=False), \
             patch.object(ops_tools, "_launch_cdp_instance",
                          return_value={"ok": True, "endpoint": "http://127.0.0.1:9222",
                                        "user_data_dir": r"C:\X\chrome-cdp"}) as launch, \
             patch.object(ops_tools, "_connect_cdp_session",
                          return_value={"pages": [], "active": 0, "cdp": True}), \
             patch.object(ops_tools, "_tabs", return_value=[]):
            r = ops_tools._attach_visible_browser(
                {"browser": "chrome", "port": 9222}, "sid", MagicMock())
        self.assertTrue(r["ok"])
        self.assertTrue(r["attached"])
        self.assertTrue(r["auto_launched"])
        self.assertEqual(r["evidence"]["browser_profile"], "dedicated_cdp_profile")
        launch.assert_called_once()

    def test_reuses_live_endpoint_without_launching(self):
        # si YA hay un endpoint vivo (instancia previa), no relanza.
        with patch.object(ops_tools, "_cdp_endpoint_alive", return_value=True), \
             patch.object(ops_tools, "_launch_cdp_instance") as launch, \
             patch.object(ops_tools, "_connect_cdp_session",
                          return_value={"pages": [], "active": 0, "cdp": True}), \
             patch.object(ops_tools, "_tabs", return_value=[]):
            r = ops_tools._attach_visible_browser(
                {"browser": "chrome", "port": 9222}, "sid", MagicMock())
        self.assertTrue(r["ok"])
        self.assertFalse(r["auto_launched"])
        launch.assert_not_called()

    def test_degrades_to_needs_user_when_launch_fails(self):
        # si el launch no produce endpoint, degradación HONESTA con instrucciones.
        with patch.object(ops_tools, "_cdp_endpoint_alive", return_value=False), \
             patch.object(ops_tools, "_launch_cdp_instance",
                          return_value={"ok": False, "error": "opera no expuso CDP"}):
            r = ops_tools._attach_visible_browser(
                {"browser": "opera", "port": 9222}, "sid", MagicMock())
        self.assertFalse(r["ok"])
        self.assertEqual(r["completion_status"], "needs_browser_debug_port")
        self.assertEqual(r["auto_launch_error"], "opera no expuso CDP")
        self.assertIn("launch_instructions", r)

    def test_auto_launch_can_be_disabled(self):
        with patch.object(ops_tools, "_cdp_endpoint_alive", return_value=False), \
             patch.object(ops_tools, "_launch_cdp_instance") as launch:
            r = ops_tools._attach_visible_browser(
                {"browser": "chrome", "port": 9222, "auto_launch": False}, "sid", MagicMock())
        self.assertFalse(r["ok"])
        self.assertEqual(r["completion_status"], "needs_browser_debug_port")
        launch.assert_not_called()


class LaunchCdpInstanceTest(unittest.TestCase):
    """El launcher mismo: mockea subprocess.Popen y el probe del endpoint para no
    lanzar un navegador real."""

    def test_launch_polls_until_endpoint_alive(self):
        alive = iter([False, False, True])
        with patch.object(ops_tools, "_resolve_browser_exe", return_value=r"C:\chrome.exe"), \
             patch.object(ops_tools.subprocess, "Popen") as popen, \
             patch.object(ops_tools, "_cdp_endpoint_alive", side_effect=lambda ep: next(alive)), \
             patch.object(ops_tools.time, "sleep"):
            r = ops_tools._launch_cdp_instance("chrome", 9222, wait_s=5)
        self.assertTrue(r["ok"])
        self.assertEqual(r["endpoint"], "http://127.0.0.1:9222")
        popen.assert_called_once()
        # debe usar un user-data-dir DEDICADO, nunca el perfil default del user.
        cmd = popen.call_args.args[0]
        self.assertTrue(any("--remote-debugging-port=9222" == c for c in cmd))
        self.assertTrue(any(c.startswith("--user-data-dir=") and "chrome-cdp" in c for c in cmd))

    def test_launch_fails_when_exe_not_found(self):
        with patch.object(ops_tools, "_resolve_browser_exe", return_value=None):
            r = ops_tools._launch_cdp_instance("brave", 9222, wait_s=1)
        self.assertFalse(r["ok"])
        self.assertIn("ejecutable", r["error"])

    def test_launch_times_out_if_endpoint_never_comes_up(self):
        with patch.object(ops_tools, "_resolve_browser_exe", return_value=r"C:\opera.exe"), \
             patch.object(ops_tools.subprocess, "Popen"), \
             patch.object(ops_tools, "_cdp_endpoint_alive", return_value=False), \
             patch.object(ops_tools.time, "sleep"):
            r = ops_tools._launch_cdp_instance("opera", 9222, wait_s=2)
        self.assertFalse(r["ok"])
        self.assertIn("no expuso CDP", r["error"])


if __name__ == "__main__":
    unittest.main()
