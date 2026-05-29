"""R4 sprint 2026-05-28: tests de interoperabilidad ToolResult ↔ dict legacy.

Demuestra que un handler migrado a `ToolResult` se puede consumir
exactamente como antes (los consumers hacen `.get("ok")`, `.get("error")`
sobre el dict — el `to_dict()` los preserva).

También verifica el camino inverso: un dict legacy se puede convertir
a `ToolResult` para inspección tipada en tests sin tocar el handler.
"""
from __future__ import annotations

import unittest

from gemma4_agent._shared import _ok, _err
from gemma4_agent.tools_pkg.tool_result import ToolResult


class TestToolResultInterop(unittest.TestCase):

    def test_legacy_ok_dict_to_tool_result(self):
        legacy = _ok(opened="calculator", verified=True, verified_by="window")
        r = ToolResult.from_dict(legacy)
        self.assertTrue(r.ok)
        self.assertEqual(r.extra.get("opened"), "calculator")
        self.assertTrue(r.verified)
        self.assertEqual(r.verified_by, "window")

    def test_legacy_err_dict_to_tool_result(self):
        legacy = _err("path not found", status="needs_user", asks_for="path")
        r = ToolResult.from_dict(legacy)
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "path not found")
        self.assertEqual(r.status, "needs_user")
        self.assertEqual(r.extra.get("asks_for"), "path")

    def test_tool_result_to_dict_matches_legacy(self):
        # Hand-crafted ToolResult that mimics what _ok(...) would return.
        r = ToolResult.ok_result(opened="spotify", verified=True, verified_by="cdp")
        d = r.to_dict()
        # Same shape as if we had called _ok(opened="spotify", verified=True, verified_by="cdp").
        self.assertEqual(d.get("ok"), True)
        self.assertEqual(d.get("opened"), "spotify")
        self.assertEqual(d.get("verified"), True)
        self.assertEqual(d.get("verified_by"), "cdp")

    def test_migrated_handler_pattern(self):
        """Patrón de migración: el handler devuelve `ToolResult.ok_result(...)
        .to_dict()` por ahora, y consumers existentes siguen funcionando
        sin cambios. Cuando todos consumers tipen, se elimina `.to_dict()`."""
        def my_migrated_handler(args: dict) -> dict:
            # Versión nueva del handler: usa ToolResult adentro, exporta dict.
            return ToolResult.ok_result(
                action="open",
                opened=args.get("target", ""),
                verified=True,
                verified_by="window_focus",
            ).to_dict()

        result = my_migrated_handler({"target": "Notepad"})
        # Consumers viejos: dict access.
        self.assertTrue(result["ok"])
        self.assertEqual(result["opened"], "Notepad")
        self.assertTrue(result["verified"])

    def test_round_trip_preserves_evidence_dict(self):
        original = ToolResult.ok_result(
            evidence={"screenshot": "/tmp/x.png", "uia_count": 3},
            window_title="Calc",
        )
        d = original.to_dict()
        recovered = ToolResult.from_dict(d)
        self.assertEqual(recovered.evidence, {"screenshot": "/tmp/x.png", "uia_count": 3})
        self.assertEqual(recovered.extra.get("window_title"), "Calc")


if __name__ == "__main__":
    unittest.main()
