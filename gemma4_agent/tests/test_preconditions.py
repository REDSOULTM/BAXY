"""Catálogo de precondiciones.

Antes de actuar, chequear estado del SO (whatsapp presente). Un False MEDIDO
bloquea con needs_user; None/unknown NO bloquea (fail-open). Gated
GEMMA4_PRECONDITIONS. Checks ESTRUCTURALES (Get-AppxPackage), no keywords.

La precondición de app (`app_resolvable`) se RETIRÓ (2026-06-10): bloqueaba
execute(app.open) ANTES de t_app y mataba su fallback a sitio web ("abrí
pivigames" nunca resolvía el sitio). Su rol de honestidad lo cubren el piso
de apertura de app_open (GEMMA4_APP_OPEN_MIN_SCORE) y el guard de claims con
tools-fallidas — un test acá lo fija para que no vuelva.
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


class AppHasNoPreconditionTest(_Gate):
    def test_app_open_is_not_blocked_upstream(self):
        # FIJA la remoción: app.open NO debe bloquearse acá aunque la app no
        # resuelva — t_app decide aguas abajo (web-divert / site-fallback /
        # piso de apertura). Volver a agregar 'app' al catálogo revive el bug
        # "abrí pivigames muere en needs_user sin resolver el sitio".
        self.assertNotIn("app", PC.PRECONDITIONS_CATALOG)
        r = PC.ensure_preconditions("app", {"action": "open", "name": "pivigames"})
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

    def test_detection_error_is_fail_open(self):
        # check devuelve None (no medible) -> NO bloquear.
        with mock.patch("gemma4_agent.domain_tools._find_whatsapp_app",
                        side_effect=RuntimeError("boom")):
            r = PC.ensure_preconditions(
                "whatsapp", {"action": "send_message", "contact": "x", "text": "y"})
        self.assertIsNone(r)

    def test_read_only_action_skipped(self):
        # whatsapp.status no actúa -> no se chequea (aunque no esté instalado).
        with mock.patch("gemma4_agent.domain_tools._find_whatsapp_app",
                        return_value={"kind": None}):
            r = PC.ensure_preconditions("whatsapp", {"action": "status"})
        self.assertIsNone(r)


class GateTest(unittest.TestCase):
    def test_gate_off_is_noop(self):
        prev = os.environ.get("GEMMA4_PRECONDITIONS")
        os.environ["GEMMA4_PRECONDITIONS"] = "0"
        try:
            with mock.patch("gemma4_agent.domain_tools._find_whatsapp_app",
                            return_value={"kind": None}):
                r = PC.ensure_preconditions(
                    "whatsapp", {"action": "send_message", "contact": "x", "text": "y"})
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
    def test_dispatch_blocks_missing_whatsapp(self):
        # El dispatcher real consulta ensure_preconditions antes de ejecutar.
        from gemma4_agent.tools_pkg.tools import ToolRegistry
        reg = ToolRegistry.__new__(ToolRegistry)
        reg._impls = {"whatsapp": lambda a: {"ok": True, "sent": True}}
        reg.state = mock.MagicMock()
        reg.safety_enabled = False
        with mock.patch("gemma4_agent.domain_tools._find_whatsapp_app",
                        return_value={"kind": None}), \
             mock.patch("gemma4_agent.tools_pkg.tools._coerce_and_validate_tool_args",
                        side_effect=lambda n, a: (a, None)):
            r = reg.execute("whatsapp", {"action": "send_message",
                                         "contact": "x", "text": "y"})
        self.assertFalse(r["ok"])
        self.assertEqual(r.get("status"), "needs_user")


if __name__ == "__main__":
    unittest.main()
