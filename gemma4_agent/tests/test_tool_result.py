"""Tests del ToolResult dataclass.

Verifica round-trip dict <-> ToolResult y los campos tipados.
"""
from __future__ import annotations

import unittest

from gemma4_agent.tools_pkg.tool_result import ToolResult


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


class TestToolResultAPIStability(unittest.TestCase):
    """API stability tests — si esos campos/métodos cambian, los
    consumers se rompen. Hard guard contra rename accidental."""

    def test_api_constructors_exist(self):
        self.assertTrue(callable(ToolResult.ok_result))
        self.assertTrue(callable(ToolResult.err))
        self.assertTrue(callable(ToolResult.from_dict))

    def test_api_methods_exist(self):
        r = ToolResult.ok_result()
        self.assertTrue(hasattr(r, "to_dict") and callable(r.to_dict))

    def test_api_typed_fields_exist(self):
        r = ToolResult.ok_result()
        for field_name in ("ok", "error", "status", "verified",
                           "verified_by", "caveat", "evidence", "extra"):
            self.assertTrue(hasattr(r, field_name),
                            f"ToolResult.{field_name} field missing")

    def test_api_frozen_dataclass(self):
        """Debe ser frozen para ser hashable (los tests pueden
        compararlas en sets)."""
        r = ToolResult.ok_result(foo="bar")
        with self.assertRaises(Exception):  # FrozenInstanceError
            r.ok = False

    def test_api_status_defaults_to_ok(self):
        r = ToolResult.ok_result()
        self.assertEqual(r.status, "ok")

    def test_api_extra_dict_is_isolated(self):
        """`extra` no debe ser shared entre instances (mutable default)."""
        r1 = ToolResult.ok_result()
        r2 = ToolResult.ok_result()
        r1.extra["foo"] = "bar"
        self.assertNotIn("foo", r2.extra,
                         "extra dict shared between instances (mutable default bug)")


if __name__ == "__main__":
    unittest.main()
