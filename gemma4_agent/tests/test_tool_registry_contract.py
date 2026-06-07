"""Contract tests for ToolRegistry's schemas API + routine + safety paths.

Complements test_tool_dispatch_contract.py (which fixes execute()).
Freezes the schema/inventory/routine-step/safety-gate API so any
regression is caught in seconds.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ..memory_pkg.memory import MemoryStore
from ..memory_pkg.state import AgentState
from ..tools_pkg.tools import COMPOUND_TOOL_SCHEMAS, ToolRegistry


def _make_registry(safety_enabled: bool = False) -> ToolRegistry:
    tmp = Path(tempfile.mkdtemp(prefix="gemma4_tr_contract_"))
    memory = MemoryStore(tmp / "mem.json")
    state = AgentState(tmp / "data" / "state.json")
    return ToolRegistry(memory, tmp / "captures", state=state, safety_enabled=safety_enabled)


class TestSchemasAPI(unittest.TestCase):
    """schemas / schema_names / schemas_for_names form the LLM-facing surface."""

    def setUp(self) -> None:
        self.reg = _make_registry()

    def test_schemas_returns_65_entries(self) -> None:
        # El conteo crece según se agregan tools. Mantenemos un piso (no
        # debería bajar de 65) pero permitimos crecimiento.
        out = self.reg.schemas
        self.assertIsInstance(out, list)
        self.assertGreaterEqual(len(out), 65)

    def test_each_schema_has_openai_function_shape(self) -> None:
        for schema in self.reg.schemas:
            self.assertIsInstance(schema, dict)
            self.assertEqual(schema.get("type"), "function")
            fn = schema.get("function")
            self.assertIsInstance(fn, dict)
            self.assertIsInstance(fn.get("name"), str)
            self.assertTrue(fn["name"], "function.name must be non-empty")
            self.assertIsInstance(fn.get("description"), str)
            self.assertIsInstance(fn.get("parameters"), dict)

    def test_schema_names_is_list_of_65_unique_strings(self) -> None:
        # Piso 65; lo que importa es uniqueness.
        names = self.reg.schema_names
        self.assertIsInstance(names, list)
        self.assertGreaterEqual(len(names), 65)
        self.assertEqual(len(set(names)), len(names), "schema_names must be unique")
        for n in names:
            self.assertIsInstance(n, str)
            self.assertTrue(n)

    def test_schemas_for_names_filters_to_requested_subset(self) -> None:
        subset = self.reg.schemas_for_names(["audio", "media"])
        names = [s["function"]["name"] for s in subset]
        self.assertEqual(set(names), {"audio", "media"})
        self.assertEqual(len(subset), 2)

    def test_schemas_for_names_ignores_unknown_names_silently(self) -> None:
        subset = self.reg.schemas_for_names(["audio", "nonexistent_tool_xyz"])
        names = [s["function"]["name"] for s in subset]
        self.assertEqual(names, ["audio"])

    def test_schemas_for_names_empty_input_yields_empty_list(self) -> None:
        self.assertEqual(self.reg.schemas_for_names([]), [])
        self.assertEqual(self.reg.schemas_for_names(set()), [])

    def test_schemas_for_names_accepts_set_and_tuple(self) -> None:
        # The annotation allows list/tuple/set; verify all three work.
        as_set = self.reg.schemas_for_names({"audio"})
        as_tuple = self.reg.schemas_for_names(("audio",))
        as_list = self.reg.schemas_for_names(["audio"])
        self.assertEqual(len(as_set), 1)
        self.assertEqual(len(as_tuple), 1)
        self.assertEqual(len(as_list), 1)


class TestImplsIntegrity(unittest.TestCase):
    """Anti-regression: _impls must have exactly one entry per compound schema."""

    def setUp(self) -> None:
        self.reg = _make_registry()

    def test_impls_has_exactly_65_entries(self) -> None:
        # Piso 65.
        self.assertGreaterEqual(len(self.reg._impls), 65)

    def test_impls_keys_match_compound_schema_names(self) -> None:
        impl_names = set(self.reg._impls.keys())
        schema_names = {s["function"]["name"] for s in COMPOUND_TOOL_SCHEMAS}
        self.assertEqual(impl_names, schema_names)

    def test_every_impl_is_callable(self) -> None:
        for name, impl in self.reg._impls.items():
            self.assertTrue(callable(impl), f"_impls[{name!r}] is not callable")


class TestRoutineStep(unittest.TestCase):
    """execute_routine_step injects routine_context + confirmed_at_create."""

    def setUp(self) -> None:
        self.reg = _make_registry()
        self._captured: dict | None = None

        def _capture(args):
            # Persist the args the handler actually saw.
            self._captured = dict(args)
            return {"ok": True, "status": "ok"}

        # Hijack `system` to capture without running the real handler.
        self.reg._impls["system"] = _capture

    def test_routine_step_injects_flags(self) -> None:
        self.reg.execute_routine_step("system", {"action": "time"}, confirmed_at_create=True)
        self.assertIsNotNone(self._captured)
        self.assertEqual(self._captured["routine_context"], True)
        self.assertEqual(self._captured["confirmed_at_create"], True)

    def test_routine_step_strips_llm_injected_flags(self) -> None:
        # The LLM is not allowed to inject these — the runner must clean them
        # before re-adding the trusted ones.
        self.reg.execute_routine_step(
            "system",
            {"action": "time", "routine_context": "MALICIOUS", "_internal_safe": True},
            confirmed_at_create=False,
        )
        self.assertEqual(self._captured["routine_context"], True)
        # confirmed_at_create comes from the kwarg, not the args dict.
        self.assertEqual(self._captured["confirmed_at_create"], False)

    def test_routine_step_unknown_tool_normalized(self) -> None:
        out = self.reg.execute_routine_step("nonexistent_xyz", {}, confirmed_at_create=True)
        self.assertEqual(out["ok"], False)
        self.assertEqual(out["status"], "failed")


class TestSafetyGate(unittest.TestCase):
    """safety_enabled=True blocks risky tools unless confirmed=True."""

    def test_safety_off_lets_risky_tool_through(self) -> None:
        reg = _make_registry(safety_enabled=False)
        # `app.close` is in the safety classifier's list. Off → no gate.
        out = reg.execute("app", {"action": "close", "name": "nonexistent_app_xyz"})
        # Whatever the handler returns is fine; what matters is that we DID
        # reach the handler — status must not be "needs_confirmation".
        self.assertNotEqual(out.get("status"), "needs_confirmation")

    def test_safety_on_blocks_app_close_without_confirmed(self) -> None:
        reg = _make_registry(safety_enabled=True)
        out = reg.execute("app", {"action": "close", "name": "nonexistent_app_xyz"})
        self.assertEqual(out["status"], "needs_confirmation")
        self.assertEqual(out["ok"], False)
        self.assertIn("confirmation", out)

    def test_safety_on_llm_confirmed_still_gated(self) -> None:
        # FIX #2 (cacería t1-4): un `confirmed:True` AUTO-EMITIDO por el LLM NO
        # saltea el gate de una acción que requiere confirmación (app.close es
        # disruptivo). El 4B aprendió a auto-confirmar; el gate lo ignora y pide
        # confirmación real. Antes procedía (bypass que cerraba apps sin confirmar).
        reg = _make_registry(safety_enabled=True)
        out = reg.execute(
            "app",
            {"action": "close", "name": "nonexistent_app_xyz", "confirmed": True},
        )
        self.assertEqual(out.get("status"), "needs_confirmation")

    def test_safety_on_passes_with_real_gate_confirmation(self) -> None:
        # La confirmación REAL (canal interno `_confirmed_by_gate`, vía safety(confirm)
        # tras round-trip del usuario) SÍ saltea el gate. No falsificable por el LLM.
        reg = _make_registry(safety_enabled=True)
        out = reg.execute(
            "app",
            {"action": "close", "name": "nonexistent_app_xyz", "_confirmed_by_gate": True},
        )
        # Llegó al handler (puede fallar porque la app no existe) pero NO está gateado.
        self.assertNotEqual(out.get("status"), "needs_confirmation")

    def test_safety_tool_itself_is_never_gated(self) -> None:
        # The `safety` tool runs confirmations themselves; gating it would
        # deadlock the agent.
        reg = _make_registry(safety_enabled=True)
        out = reg.execute("safety", {"action": "status"})
        self.assertNotEqual(out.get("status"), "needs_confirmation")


class TestParentAgentBackref(unittest.TestCase):
    """ToolRegistry exposes parent_agent so `subagent` can recurse into a
    fresh Gemma4Agent rooted at the same config."""

    def test_parent_agent_defaults_to_none_via_getattr(self) -> None:
        reg = _make_registry()
        # The attribute is not set in __init__; agent.py sets it post-construct.
        # The contract: consumers must access it via getattr(reg, "parent_agent", None).
        self.assertIsNone(getattr(reg, "parent_agent", None))

    def test_parent_agent_can_be_set(self) -> None:
        reg = _make_registry()
        sentinel = object()
        reg.parent_agent = sentinel  # type: ignore[attr-defined]
        self.assertIs(getattr(reg, "parent_agent", None), sentinel)


class TestToolNameNormalization(unittest.TestCase):
    """Gemma 4 ensucia el nombre de la tool (mayúsculas, parens, segmentos,
    prefijo de acción). La normalización estructural lo arregla; un nombre
    genuinamente inexistente sigue siendo 'unknown tool'."""

    def setUp(self) -> None:
        self.reg = _make_registry()

    def test_uppercase_dispatches(self) -> None:
        r = self.reg.execute("SYSTEM", {"action": "time"})
        self.assertNotIn("unknown tool", str(r.get("error") or ""))
        self.assertTrue(r.get("ok"))

    def test_dirty_forms_map_to_base(self) -> None:
        from ..tools_pkg.tools import _normalize_tool_name
        known = set(self.reg._impls.keys())
        for dirty, base in (("gui()", "gui"), ("Functions.gui.click", "gui"),
                            ("gui_click", "gui"), ("gui ", "gui"),
                            ("tools/window", "window")):
            if base in known:
                self.assertEqual(_normalize_tool_name(dirty, known), base, dirty)

    def test_genuinely_unknown_stays_unknown(self) -> None:
        r = self.reg.execute("teleport", {"x": 1})
        self.assertIn("unknown tool", str(r.get("error") or ""))

    def test_normalize_returns_none_for_unknown(self) -> None:
        from ..tools_pkg.tools import _normalize_tool_name
        known = {"gui", "audio", "system"}
        self.assertIsNone(_normalize_tool_name("frobnicate", known))
        self.assertIsNone(_normalize_tool_name("xyz_abc", known))


if __name__ == "__main__":
    unittest.main()
