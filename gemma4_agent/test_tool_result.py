"""R4 sprint 2026-05-28: tests del ToolResult dataclass.

Verifica round-trip dict <-> ToolResult y los campos tipados.
"""
from __future__ import annotations

import unittest

from gemma4_agent.tool_result import ToolResult


class TestToolResult(unittest.TestCase):

    def test_ok_minimal(self):
        r = ToolResult.ok_result()
        self.assertTrue(r.ok)
        self.assertEqual(r.error, "")
        self.assertEqual(r.status, "ok")
        d = r.to_dict()
        self.assertEqual(d, {"ok": True})

    def test_err_minimal(self):
        r = ToolResult.err("boom")
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "boom")
        d = r.to_dict()
        self.assertEqual(d, {"ok": False, "error": "boom"})

    def test_typed_fields_round_trip(self):
        r = ToolResult.ok_result(
            verified=True,
            verified_by="uia",
            caveat="ventana detrás",
            evidence={"window_title": "Calculadora"},
            opened="calculator",  # goes to extra
            verified_count=3,
        )
        self.assertTrue(r.verified)
        self.assertEqual(r.verified_by, "uia")
        self.assertEqual(r.caveat, "ventana detrás")
        self.assertEqual(r.evidence, {"window_title": "Calculadora"})
        self.assertEqual(r.extra, {"opened": "calculator", "verified_count": 3})

    def test_to_dict_roundtrip(self):
        original = {
            "ok": True,
            "status": "attempted",
            "verified": False,
            "verified_by": "screenshot",
            "caveat": "no pude confirmar",
            "evidence": {"shot": "/tmp/x.png"},
            "opened": "spotify",
        }
        r = ToolResult.from_dict(original)
        self.assertEqual(r.to_dict(), original)

    def test_needs_user_status(self):
        r = ToolResult.err("missing creds", status="needs_user", asks_for="token")
        d = r.to_dict()
        self.assertEqual(d, {
            "ok": False,
            "error": "missing creds",
            "status": "needs_user",
            "asks_for": "token",
        })

    def test_extra_not_clobbered_by_typed_fields(self):
        r = ToolResult.ok_result(my_field="X", another=42)
        self.assertEqual(r.extra["my_field"], "X")
        self.assertEqual(r.extra["another"], 42)


if __name__ == "__main__":
    unittest.main()
