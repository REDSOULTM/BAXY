"""Tests del cache por-subset de ToolRegistry.schemas_for_names (2026-06-02).

GATE de la tarea:
  (b) EQUIVALENCIA: con cache devuelve EXACTAMENTE lo mismo que sin cache.
  (c) INVALIDACION: cambiar LEAN -> no sirve stale; subsets MCP bypasean el cache.
  (d) micro-bench (sanity, no es un gate de tiempo duro -> el ahorro MEDIDO es
      ~13 us/call = 0.013 ms, despreciable; ver el reporte). Aca solo verificamos
      que el hit no rehace el trabajo (misma entry, mismo contenido).

No requiere modelo/GPU. Mockea solo el cliente MCP donde hace falta.
"""
import os
import tempfile
import unittest
from pathlib import Path

from ..memory_pkg.memory import MemoryStore
from ..memory_pkg.state import AgentState
from ..tools_pkg import tools as T
from ..tools_pkg.tools import ToolRegistry


def _make_registry() -> ToolRegistry:
    tmp = Path(tempfile.mkdtemp(prefix="gemma4_cache_"))
    memory = MemoryStore(tmp / "mem.json")
    state = AgentState(tmp / "data" / "state.json")
    return ToolRegistry(memory, tmp / "captures", state=state, safety_enabled=False)


class _LeanEnv:
    """Fija GEMMA4_LEAN_RULES (restaura al salir)."""

    def __init__(self, on: bool):
        self.on = on
        self.prev = None

    def __enter__(self):
        self.prev = os.environ.get("GEMMA4_LEAN_RULES")
        os.environ["GEMMA4_LEAN_RULES"] = "1" if self.on else "0"
        return self

    def __exit__(self, *exc):
        if self.prev is None:
            os.environ.pop("GEMMA4_LEAN_RULES", None)
        else:
            os.environ["GEMMA4_LEAN_RULES"] = self.prev


class TestSchemasForNamesCache(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = _make_registry()
        T._invalidate_schemas_cache()

    def tearDown(self) -> None:
        T._invalidate_schemas_cache()

    def test_cache_hit_equals_cold_compute(self) -> None:
        subset = ["audio", "media", "whatsapp"]
        cold = self.reg.schemas_for_names(subset)
        hot = self.reg.schemas_for_names(subset)
        self.assertEqual(cold, hot)
        self.assertEqual(
            [s["function"]["name"] for s in cold],
            [s["function"]["name"] for s in hot],
        )

    def test_cache_matches_uncached_reference(self) -> None:
        # La salida respeta el ORDEN de `subset` (anti-primacy del router), no el
        # orden global de COMPOUND_TOOL_SCHEMAS. La referencia se ordena por la
        # posicion en subset para reflejar el contrato actual.
        subset = ["audio", "media", "window", "gui"]
        with _LeanEnv(True):
            T._invalidate_schemas_cache()
            got = self.reg.schemas_for_names(subset)
            wanted = set(subset)
            pos = {n: i for i, n in enumerate(subset)}
            ref = [s for s in T.COMPOUND_TOOL_SCHEMAS
                   if s.get("function", {}).get("name") in wanted]
            ref.sort(key=lambda s: pos.get(s.get("function", {}).get("name"), len(pos)))
            ref = [T._with_lean_description(s) for s in ref]
            self.assertEqual(got, ref)
            self.assertEqual(
                [s["function"]["name"] for s in got], subset,
                "schemas_for_names debe devolver en el ORDEN pedido (anti-primacy)")

    def test_order_preserving_key(self) -> None:
        # El orden de `names` IMPORTA: es el reorden anti-primacy del router (tool
        # de mayor score primero, contra el primacy bias del 4B). Dos subsets con
        # las mismas tools en distinto orden son entradas de cache DISTINTAS — si
        # colisionaran, el cache congelaria el primer orden y la feature
        # anti-primacy volveria a quedar inerte (era el bug original).
        T._invalidate_schemas_cache()
        a = self.reg.schemas_for_names(["audio", "media", "window"])
        b = self.reg.schemas_for_names(["window", "media", "audio"])
        self.assertEqual([s["function"]["name"] for s in a], ["audio", "media", "window"])
        self.assertEqual([s["function"]["name"] for s in b], ["window", "media", "audio"])
        self.assertNotEqual(a, b)  # distinto orden -> distinta salida
        self.assertEqual(len(T._SCHEMAS_FOR_NAMES_CACHE), 2)  # 2 claves distintas

    def test_returned_list_is_defensive_copy(self) -> None:
        subset = ["audio", "media"]
        first = self.reg.schemas_for_names(subset)
        first.append({"poison": True})
        second = self.reg.schemas_for_names(subset)
        self.assertNotIn({"poison": True}, second)
        self.assertEqual(len(second), 2)

    def test_empty_and_unknown(self) -> None:
        self.assertEqual(self.reg.schemas_for_names([]), [])
        only_audio = self.reg.schemas_for_names(["audio", "nope_xyz"])
        self.assertEqual([s["function"]["name"] for s in only_audio], ["audio"])

    def test_lean_toggle_not_stale(self) -> None:
        subset = ["whatsapp"]
        with _LeanEnv(True):
            lean = self.reg.schemas_for_names(subset)
        with _LeanEnv(False):
            full = self.reg.schemas_for_names(subset)
        lean_desc = lean[0]["function"]["description"]
        full_desc = full[0]["function"]["description"]
        self.assertNotEqual(lean_desc, full_desc)
        self.assertEqual(lean_desc, T.LEAN_DESCRIPTIONS["whatsapp"])
        self.assertEqual(len(T._SCHEMAS_FOR_NAMES_CACHE), 2)

    def test_lean_state_keyed_no_crosstalk(self) -> None:
        subset = ["audio"]
        with _LeanEnv(True):
            l1 = self.reg.schemas_for_names(subset)[0]["function"]["description"]
        with _LeanEnv(False):
            f1 = self.reg.schemas_for_names(subset)[0]["function"]["description"]
        with _LeanEnv(True):
            l2 = self.reg.schemas_for_names(subset)[0]["function"]["description"]
        self.assertEqual(l1, l2)
        self.assertNotEqual(l1, f1)
        self.assertEqual(l1, T.LEAN_DESCRIPTIONS["audio"])

    def test_mcp_subset_bypasses_cache(self) -> None:
        T._invalidate_schemas_cache()
        import gemma4_agent.tools_pkg.mcp_client as mc

        def fake_v1():
            return [{
                "type": "function",
                "function": {"name": "mcp__fs__read", "description": "v1",
                             "parameters": {"type": "object", "properties": {}}},
            }]

        orig = mc.mcp_tool_schemas
        mc.mcp_tool_schemas = fake_v1
        try:
            r1 = self.reg.schemas_for_names(["audio", "mcp__fs__read"])
            names1 = [s["function"]["name"] for s in r1]
            self.assertIn("mcp__fs__read", names1)
            self.assertIn("audio", names1)
            self.assertEqual(len(T._SCHEMAS_FOR_NAMES_CACHE), 0)

            def fake_v2():
                return [{
                    "type": "function",
                    "function": {"name": "mcp__fs__read", "description": "v2-CHANGED",
                                 "parameters": {"type": "object", "properties": {}}},
                }]
            mc.mcp_tool_schemas = fake_v2
            r2 = self.reg.schemas_for_names(["audio", "mcp__fs__read"])
            mcp_desc = next(s["function"]["description"] for s in r2
                            if s["function"]["name"] == "mcp__fs__read")
            self.assertEqual(mcp_desc, "v2-CHANGED")
        finally:
            mc.mcp_tool_schemas = orig

    def test_invalidate_clears(self) -> None:
        self.reg.schemas_for_names(["audio"])
        self.assertGreaterEqual(len(T._SCHEMAS_FOR_NAMES_CACHE), 1)
        T._invalidate_schemas_cache()
        self.assertEqual(len(T._SCHEMAS_FOR_NAMES_CACHE), 0)

    def test_second_call_uses_cache(self) -> None:
        T._invalidate_schemas_cache()
        self.reg.schemas_for_names(["audio", "media", "window"])
        n1 = len(T._SCHEMAS_FOR_NAMES_CACHE)
        self.reg.schemas_for_names(["audio", "media", "window"])
        n2 = len(T._SCHEMAS_FOR_NAMES_CACHE)
        self.assertEqual(n1, 1)
        self.assertEqual(n2, 1)


if __name__ == "__main__":
    unittest.main()
