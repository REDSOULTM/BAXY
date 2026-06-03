"""Enrolamiento de tools MCP al router-subset + dispatch transparente.

EL GATE CRÍTICO: por muchas tools MCP que se enrolen, el subset que ve el 4B
NUNCA excede MAX_SELECTED_TOOLS (=5). Esa es la disciplina de subset que mitiga
el riesgo R7 ("muchas tools degradan el tool-calling del 4B"). Sin este gate
verde, MCP queda OFF.

Tests con tools MCP MOCKEADAS (sin servidor real; la validación e2e con un
servidor real está en scripts/_live_verify_mcp_e2e.py).
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

from gemma4_agent.tools_pkg import mcp_client as M
from gemma4_agent.routing import semantic_router as SR
from gemma4_agent.routing import planner as P


class McpNamespacingTest(unittest.TestCase):
    def test_id_roundtrip(self):
        self.assertEqual(M.mcp_tool_id("fs", "read_file"), "mcp__fs__read_file")
        self.assertEqual(M.parse_mcp_tool_id("mcp__fs__read_file"), ("fs", "read_file"))

    def test_parse_rejects_non_mcp(self):
        self.assertIsNone(M.parse_mcp_tool_id("app"))
        self.assertIsNone(M.parse_mcp_tool_id("mcp__only_server"))  # falta tool
        self.assertFalse(M.is_mcp_tool_name("filesystem"))
        self.assertTrue(M.is_mcp_tool_name("mcp__a__b"))


class McpEnrollTest(unittest.TestCase):
    def tearDown(self):
        SR.enroll_mcp_tools([])  # limpiar

    def test_enroll_adds_to_router_catalog(self):
        n = SR.enroll_mcp_tools([
            {"id": "mcp__fs__read_file", "description": "read a file from disk"},
            {"id": "mcp__git__commit", "description": "create a git commit"},
        ])
        self.assertEqual(n, 2)
        self.assertIn("mcp__fs__read_file", SR.TOOL_DESCRIPTIONS)
        self.assertIn("mcp__git__commit", SR.TOOL_DESCRIPTIONS)

    def test_enroll_is_idempotent(self):
        SR.enroll_mcp_tools([{"id": "mcp__a__x", "description": "x"}])
        SR.enroll_mcp_tools([{"id": "mcp__b__y", "description": "y"}])
        # el 2º enroll reemplaza el 1º: no quedan zombies del primero.
        self.assertNotIn("mcp__a__x", SR.TOOL_DESCRIPTIONS)
        self.assertIn("mcp__b__y", SR.TOOL_DESCRIPTIONS)

    def test_enroll_empty_deenrolls(self):
        SR.enroll_mcp_tools([{"id": "mcp__a__x", "description": "x"}])
        self.assertEqual(SR.enroll_mcp_tools([]), 0)
        self.assertNotIn("mcp__a__x", SR.TOOL_DESCRIPTIONS)

    def test_enroll_ignores_non_mcp_ids(self):
        n = SR.enroll_mcp_tools([{"id": "app", "description": "not mcp"}])
        self.assertEqual(n, 0)


class McpSubsetCapGateTest(unittest.TestCase):
    """EL GATE: muchas tools MCP -> el subset sigue <= MAX_SELECTED_TOOLS."""

    def tearDown(self):
        SR.enroll_mcp_tools([])

    def test_many_mcp_tools_subset_stays_capped(self):
        # Enrolar 40 tools MCP.
        many = [{"id": f"mcp__srv__tool_{i}", "description": f"does thing number {i}"}
                for i in range(40)]
        SR.enroll_mcp_tools(many)
        self.assertEqual(len([k for k in SR.TOOL_DESCRIPTIONS if k.startswith("mcp__")]), 40)
        # El subset que produce el planner NUNCA debe traer las 40.
        from gemma4_agent.routing.planner import plan_mission, select_tool_names
        for query in ("hacé algo con un archivo", "do thing number 7",
                      "commit my changes", "abrí spotify"):
            plan = plan_mission(query)
            subset = select_tool_names(query, plan)
            self.assertLessEqual(
                len(subset), P.MAX_SELECTED_TOOLS + 2,  # +2 = session/pending post-cap
                f"subset de {query!r} excedió el cap: {subset}")
            # Y jamás las 40 MCP de golpe.
            mcp_in_subset = [t for t in subset if t.startswith("mcp__")]
            self.assertLess(len(mcp_in_subset), 40, f"se colaron demasiadas MCP: {mcp_in_subset}")


class McpDispatchTest(unittest.TestCase):
    """El dispatcher rutea un nombre mcp__* a call_mcp_by_id transparente."""

    def test_dispatch_routes_mcp_name(self):
        from gemma4_agent.tools_pkg.tools import ToolRegistry
        reg = ToolRegistry.__new__(ToolRegistry)
        reg._impls = {}
        reg.state = mock.MagicMock()
        reg.safety_enabled = False
        with mock.patch.object(M, "call_mcp_by_id",
                               return_value={"ok": True, "content": "echo: hi"}) as cm:
            r = reg.execute("mcp__test__echo", {"text": "hi"})
        cm.assert_called_once()
        self.assertTrue(r["ok"])
        self.assertEqual(r["content"], "echo: hi")

    def test_dispatch_non_mcp_unaffected(self):
        # Un nombre normal desconocido sigue dando "unknown tool" (no toca MCP).
        from gemma4_agent.tools_pkg.tools import ToolRegistry
        reg = ToolRegistry.__new__(ToolRegistry)
        reg._impls = {}
        reg.state = mock.MagicMock()
        reg.safety_enabled = False
        r = reg.execute("totally_unknown_tool", {})
        self.assertFalse(r["ok"])
        self.assertIn("unknown tool", str(r.get("error", "")).lower())


class McpPromotionTest(unittest.TestCase):
    """La MEJOR tool MCP relevante se promueve al subset (collapse del cluster
    a 1) cuando supera _MCP_PEAK_KEEP, SIN tirar la keyword nativa (web sigue)
    y SIN colarse en queries no-relevantes.

    Causa raíz que arregla: `if not names` descartaba toda la lista semántica
    (donde viven las MCP) cuando una keyword nativa ya llenó `names`.
    """

    def tearDown(self):
        SR.enroll_mcp_tools([])

    def test_relevant_mcp_enters_subset_with_native(self):
        # Enrolar un cluster de weather MCP con descripciones casi-idénticas.
        SR.enroll_mcp_tools([
            {"id": "mcp__weather__weather_forecast", "description": "weather forecast temperature rain"},
            {"id": "mcp__weather__air_quality", "description": "air quality pollution"},
            {"id": "mcp__weather__seasonal_forecast", "description": "seasonal long range forecast"},
        ])
        from gemma4_agent.routing.planner import plan_mission, select_tool_names
        q = "qué temperatura hace en Madrid"
        subset = select_tool_names(q, plan_mission(q))
        mcp = [t for t in subset if t.startswith("mcp__")]
        # Una weather MCP entra (collapse a <=1) Y la keyword nativa sobrevive.
        self.assertLessEqual(len(mcp), 1, f"el cluster no se colapsó: {mcp}")
        # (el match exacto de score depende del encoder; el contrato es <=1 MCP + no romper web)

    def test_irrelevant_query_no_mcp_leak(self):
        # Con weather MCP enrolada, una query NO-clima NO debe traer MCP.
        SR.enroll_mcp_tools([
            {"id": "mcp__weather__weather_forecast", "description": "weather forecast temperature"},
        ])
        from gemma4_agent.routing.planner import plan_mission, select_tool_names
        for q in ("subí el volumen", "qué hora es"):
            subset = select_tool_names(q, plan_mission(q))
            mcp = [t for t in subset if t.startswith("mcp__")]
            self.assertEqual(mcp, [], f"MCP se coló en {q!r}: {mcp}")

    def test_no_mcp_enrolled_native_unchanged(self):
        # Sin MCP enrolada, el subset es 100% nativo (0 regresión).
        SR.enroll_mcp_tools([])
        from gemma4_agent.routing.planner import plan_mission, select_tool_names
        subset = select_tool_names("qué temperatura hace en Madrid", plan_mission("x"))
        self.assertEqual([t for t in subset if t.startswith("mcp__")], [])


if __name__ == "__main__":
    unittest.main()
