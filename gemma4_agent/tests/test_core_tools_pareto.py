"""Tests del set CORE adaptativo por usuario (Camino C dinamico, 2026-05-28).

Verifica:
  - Default global cuando no hay cache de usuario
  - Lectura/persistencia de ~/.gemma4/core_tools_pareto.json
  - Computo desde trace.jsonl (min calls, ordenamiento por Pareto)
  - Histeresis: no persistir si el cambio es chico (Jaccard < threshold)
  - Estabilidad de bytes (sorted)
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gemma4_agent.agent_core import core_tools_pareto as ctp


class TestDefaultCoreTools(unittest.TestCase):
    def test_default_has_6_items(self):
        # v22 2026-05-28 (Plan A2, commit 3898a54): 6 tools universales por voz
        # (vs los 15 previos) -> system prompt ~5k tok. Validado EN VIVO 8/8.
        self.assertEqual(len(ctp._default_core_tools()), 6)

    def test_default_is_sorted_for_byte_stability(self):
        default = ctp._default_core_tools()
        self.assertEqual(list(default), sorted(default))


class TestReadUserCoreTools(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._orig_path = ctp._CORE_TOOLS_PATH

    def tearDown(self):
        ctp._CORE_TOOLS_PATH = self._orig_path

    def test_returns_default_when_no_file(self):
        ctp._CORE_TOOLS_PATH = self.tmp / "doesnotexist.json"
        result = ctp.read_user_core_tools()
        self.assertEqual(result, ctp._default_core_tools())

    def test_reads_user_file_when_present(self):
        path = self.tmp / "core_tools_pareto.json"
        path.write_text(json.dumps({"tools": ["whatsapp", "browser", "app",
                                              "web", "media"]}),
                        encoding="utf-8")
        ctp._CORE_TOOLS_PATH = path
        result = ctp.read_user_core_tools()
        # Sorted para byte-stability
        self.assertEqual(result, ("app", "browser", "media", "web", "whatsapp"))

    def test_invalid_json_falls_back_to_default(self):
        path = self.tmp / "core_tools_pareto.json"
        path.write_text("{ broken json", encoding="utf-8")
        ctp._CORE_TOOLS_PATH = path
        result = ctp.read_user_core_tools()
        self.assertEqual(result, ctp._default_core_tools())

    def test_too_few_tools_falls_back_to_default(self):
        path = self.tmp / "core_tools_pareto.json"
        path.write_text(json.dumps({"tools": ["app", "browser"]}),
                        encoding="utf-8")
        ctp._CORE_TOOLS_PATH = path
        result = ctp.read_user_core_tools()
        # < 5 tools => default
        self.assertEqual(result, ctp._default_core_tools())


class TestComputeCoreToolsFromTrace(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.trace = self.tmp / "traces.jsonl"

    def _write_trace(self, tool_calls: list[str]):
        """Helper: escribe N tool_call events al trace."""
        lines = []
        for name in tool_calls:
            lines.append(json.dumps({
                "ts": "2026-05-28T12:00:00",
                "turn_id": "x",
                "kind": "tool_call",
                "name": name,
            }))
        self.trace.write_text("\n".join(lines), encoding="utf-8")

    def test_returns_none_when_trace_missing(self):
        result = ctp.compute_core_tools_from_trace(self.tmp / "nope.jsonl")
        self.assertIsNone(result)

    def test_returns_none_when_too_few_calls(self):
        self._write_trace(["app"] * 50)  # min_calls=100
        result = ctp.compute_core_tools_from_trace(self.trace, min_calls=100)
        self.assertIsNone(result)

    def test_picks_top_tools_by_frequency(self):
        # Patron sintetico: app es el mas usado, browser segundo
        calls = (["app"] * 200 + ["browser"] * 150 + ["web"] * 100 +
                 ["media"] * 80 + ["audio"] * 60 + ["gui"] * 50)
        self._write_trace(calls)
        result = ctp.compute_core_tools_from_trace(self.trace, size=4,
                                                    min_calls=100)
        # Sorted, top 4 = app, browser, media, web (orden alfabetico de top-N)
        self.assertEqual(result, ("app", "browser", "media", "web"))

    def test_ignores_non_tool_call_events(self):
        # Mezcla tool_call con otros eventos para verificar el filtro
        events = []
        for _ in range(100):
            events.append(json.dumps({
                "ts": "x", "turn_id": "y", "kind": "tool_call", "name": "app"
            }))
        for _ in range(200):
            events.append(json.dumps({
                "ts": "x", "turn_id": "y", "kind": "llm_response",
                "name": "browser"  # name aqui NO cuenta (kind != tool_call)
            }))
        self.trace.write_text("\n".join(events), encoding="utf-8")
        result = ctp.compute_core_tools_from_trace(self.trace, size=5,
                                                    min_calls=50)
        # Solo app entra (100 tool_calls). El resto del top deberia ser
        # vacio pero como hay solo 1 stem unico, el set deberia tener < 5
        # -> None.
        self.assertIsNone(result)


class TestJaccardDistance(unittest.TestCase):
    def test_identical_sets_distance_zero(self):
        a = ("app", "browser", "media")
        self.assertEqual(ctp._jaccard_distance(a, a), 0.0)

    def test_disjoint_sets_distance_one(self):
        a = ("app", "browser")
        b = ("vision", "whatsapp")
        self.assertEqual(ctp._jaccard_distance(a, b), 1.0)

    def test_half_overlap(self):
        a = ("app", "browser")
        b = ("app", "vision")
        # |inter| = 1, |union| = 3 -> Jaccard sim = 1/3 -> distance = 2/3
        self.assertAlmostEqual(ctp._jaccard_distance(a, b), 2/3, places=5)


class TestRecomputeAndPersist(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._orig_path = ctp._CORE_TOOLS_PATH
        self._orig_home = ctp._USER_HOME
        ctp._USER_HOME = self.tmp
        ctp._CORE_TOOLS_PATH = self.tmp / "core_tools_pareto.json"
        self.trace = self.tmp / "traces.jsonl"

    def tearDown(self):
        ctp._CORE_TOOLS_PATH = self._orig_path
        ctp._USER_HOME = self._orig_home

    def _write_trace(self, tool_calls: list[str]):
        lines = [json.dumps({"ts": "x", "turn_id": "y", "kind": "tool_call",
                              "name": n}) for n in tool_calls]
        self.trace.write_text("\n".join(lines), encoding="utf-8")

    def test_persists_when_no_previous_file(self):
        # Trace con set muy distinto al default
        self._write_trace(["whatsapp"] * 200 + ["email"] * 150 +
                          ["calendar"] * 100 + ["notes"] * 80 +
                          ["reminder"] * 60)
        result = ctp.recompute_and_persist(self.trace, size=5,
                                            threshold=0.20)
        self.assertIsNotNone(result)
        self.assertTrue(ctp._CORE_TOOLS_PATH.exists())
        # Verificar que persistio el SET nuevo (no el default)
        data = json.loads(ctp._CORE_TOOLS_PATH.read_text(encoding="utf-8"))
        self.assertIn("whatsapp", data["tools"])
        self.assertIn("email", data["tools"])

    def test_does_not_persist_when_change_is_small(self):
        # Primero persistimos un set base
        base = ["app", "browser", "media", "web", "audio"]
        ctp._CORE_TOOLS_PATH.write_text(json.dumps({"tools": base}),
                                         encoding="utf-8")
        # Ahora un trace que da el MISMO set
        self._write_trace(["app"] * 200 + ["browser"] * 150 +
                          ["media"] * 100 + ["web"] * 80 + ["audio"] * 60)
        result = ctp.recompute_and_persist(self.trace, size=5,
                                            threshold=0.20)
        # Debe devolver el viejo set (no cambio significativo)
        self.assertEqual(result, tuple(sorted(base)))

    def test_returns_none_when_trace_insufficient(self):
        self._write_trace(["app"] * 10)  # < min_calls
        result = ctp.recompute_and_persist(self.trace, threshold=0.20)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
