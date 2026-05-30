"""ITEM 3 (perfection roadmap 2026-05-29): catálogo de precondiciones.

Antes de actuar, chequear estado del SO (app instalable, whatsapp presente). Un
False MEDIDO bloquea con needs_user; None/unknown NO bloquea (fail-open). Gated
GEMMA4_PRECONDITIONS. Checks ESTRUCTURALES (resolver/Get-AppxPackage), no keywords.
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

from gemma4_agent.safety_pkg import preconditions as PC


class _Gate(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("GEMMA4_PRECONDITIONS")
        os.environ["GEMMA4_PRECONDITIONS"] = "1"

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("GEMMA4_PRECONDITIONS", None)
        else:
            os.environ["GEMMA4_PRECONDITIONS"] = self._prev


class AppPreconditionTest(_Gate):
    def test_missing_app_blocks(self):
        with mock.patch("gemma4_agent.tools_pkg.app_resolver.AppResolver") as AR:
            AR.return_value.find.return_value = []
            r = PC.ensure_preconditions("app", {"action": "open", "name": "ZZZ"})
        self.assertIsNotNone(r)
        self.assertEqual(r.status, PC.RESULT_NEEDS_USER)
        self.assertEqual(r.name, "app_resolvable")

    def test_present_app_passes(self):
        with mock.patch("gemma4_agent.tools_pkg.app_resolver.AppResolver") as AR:
            AR.return_value.find.return_value = [object()]
            r = PC.ensure_preconditions("app", {"action": "open", "name": "Spotify"})
        self.assertIsNone(r)

    def test_resolver_error_is_fail_open(self):
        # check devuelve None (no medible) -> NO bloquear.
        with mock.patch("gemma4_agent.tools_pkg.app_resolver.AppResolver",
                        side_effect=RuntimeError("boom")):
            r = PC.ensure_preconditions("app", {"action": "open", "name": "X"})
        self.assertIsNone(r)

    def test_non_open_action_skipped(self):
        # app.search no actúa -> no se chequea (aunque la app no resuelva).
        with mock.patch("gemma4_agent.tools_pkg.app_resolver.AppResolver") as AR:
            AR.return_value.find.return_value = []
            r = PC.ensure_preconditions("app", {"action": "search", "name": "ZZZ"})
        self.assertIsNone(r)


class WhatsappPreconditionTest(_Gate):
    def test_not_installed_blocks(self):
        with mock.patch("gemma4_agent.domain_tools._find_whatsapp_app",
                        return_value={"kind": None}):
            r = PC.ensure_preconditions(
                "whatsapp", {"action": "send_message", "contact": "x", "text": "y"})
        self.assertIsNotNone(r)
        self.assertEqual(r.status, PC.RESULT_NEEDS_USER)

    def test_installed_passes(self):
        with mock.patch("gemma4_agent.domain_tools._find_whatsapp_app",
                        return_value={"kind": "uwp"}):
            r = PC.ensure_preconditions(
                "whatsapp", {"action": "send_message", "contact": "x", "text": "y"})
        self.assertIsNone(r)


class GateTest(unittest.TestCase):
    def test_gate_off_is_noop(self):
        prev = os.environ.get("GEMMA4_PRECONDITIONS")
        os.environ["GEMMA4_PRECONDITIONS"] = "0"
        try:
            with mock.patch("gemma4_agent.tools_pkg.app_resolver.AppResolver") as AR:
                AR.return_value.find.return_value = []
                r = PC.ensure_preconditions("app", {"action": "open", "name": "ZZZ"})
            self.assertIsNone(r)  # off -> no chequea
        finally:
            if prev is None:
                os.environ.pop("GEMMA4_PRECONDITIONS", None)
            else:
                os.environ["GEMMA4_PRECONDITIONS"] = prev

    def test_unknown_tool_has_no_preconditions(self):
        os.environ["GEMMA4_PRECONDITIONS"] = "1"
        try:
            self.assertIsNone(PC.ensure_preconditions("filesystem", {"action": "read"}))
        finally:
            os.environ.pop("GEMMA4_PRECONDITIONS", None)


class DispatchIntegrationTest(_Gate):
    def test_dispatch_blocks_missing_app(self):
        # El dispatcher real consulta ensure_preconditions antes de ejecutar.
        from gemma4_agent.tools_pkg.tools import ToolRegistry
        reg = ToolRegistry.__new__(ToolRegistry)
        reg._impls = {"app": lambda a: {"ok": True, "opened": True}}
        reg.state = mock.MagicMock()
        reg.safety_enabled = False
        with mock.patch("gemma4_agent.tools_pkg.app_resolver.AppResolver") as AR, \
             mock.patch("gemma4_agent.tools_pkg.tools._coerce_and_validate_tool_args",
                        side_effect=lambda n, a: (a, None)):
            AR.return_value.find.return_value = []
            r = reg.execute("app", {"action": "open", "name": "NoExisteZZZ"})
        self.assertFalse(r["ok"])
        self.assertEqual(r.get("status"), "needs_user")


if __name__ == "__main__":
    unittest.main()
