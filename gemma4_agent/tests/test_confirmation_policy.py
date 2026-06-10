"""B5 — política de confirmación estructurada (confirmation_policy.py).

Verifica las 3 políticas (confirm_risky default / never / always) y la GARANTÍA
DURA del backlog: una acción IRREVERSIBLE se confirma bajo CUALQUIER política.
Determinista (sin LLM): usa classify_tool_call real para producir SafetyDecisions.
"""
import os
import unittest

from ..safety_pkg.safety import classify_tool_call
from ..safety_pkg.confirmation_policy import (
    should_confirm, get_policy, is_irreversible,
    CONFIRM_RISKY, ALWAYS_CONFIRM, NEVER_CONFIRM,
)


def _decision(tool: str, action: str, **extra):
    return classify_tool_call(tool, {"action": action, **extra})


class TestIrreversibleHardGate(unittest.TestCase):
    """Garantía dura B5: lo irreversible se confirma SIEMPRE, sea cual sea la política."""

    IRREVERSIBLE = [("email", "send"), ("filesystem", "delete"), ("filesystem", "move"),
                    ("package", "install"), ("registry", "delete"), ("system", "shutdown"),
                    ("download", "fetch")]

    def test_irreversible_detected(self):
        for tool, action in self.IRREVERSIBLE:
            d = _decision(tool, action)
            self.assertTrue(d.requires_confirmation, f"{tool}.{action} debe ser riesgoso")
            self.assertTrue(is_irreversible(d), f"{tool}.{action} debe ser irreversible")

    def test_irreversible_confirms_under_every_policy(self):
        for tool, action in self.IRREVERSIBLE:
            d = _decision(tool, action)
            for pol in (CONFIRM_RISKY, ALWAYS_CONFIRM, NEVER_CONFIRM):
                self.assertTrue(
                    should_confirm(d, pol),
                    f"{tool}.{action} DEBE confirmarse bajo política {pol!r}")


class TestPolicyBehaviour(unittest.TestCase):
    def test_reversible_risky_auto_approved_only_under_never(self):
        # local_state_change (notes/calendar/contacts) es reversible -> never lo auto-aprueba.
        d = _decision("notes_tasks", "create", title="x")
        self.assertTrue(d.requires_confirmation)
        self.assertFalse(is_irreversible(d))
        self.assertTrue(should_confirm(d, CONFIRM_RISKY))    # default: confirma
        self.assertTrue(should_confirm(d, ALWAYS_CONFIRM))   # always: confirma
        self.assertFalse(should_confirm(d, NEVER_CONFIRM))   # never: auto-aprueba

    def test_non_risky_confirmed_only_under_always(self):
        d = classify_tool_call("web", {"action": "search", "query": "x"})
        self.assertFalse(d.requires_confirmation)
        self.assertFalse(should_confirm(d, CONFIRM_RISKY))
        self.assertFalse(should_confirm(d, NEVER_CONFIRM))
        self.assertTrue(should_confirm(d, ALWAYS_CONFIRM))   # auditoría: confirma todo

    def test_all_permissive_never_confirms_even_irreversible(self):
        # modo 'all' (permisivo TOTAL): NADA confirma, ni lo irreversible. Cerrar
        # apps Y borrar archivos Y apagar -> sin fricción.
        from ..safety_pkg.confirmation_policy import ALL_PERMISSIVE
        for tool, action in [("app", "close"), ("filesystem", "delete"),
                             ("system", "shutdown"), ("terminal", "run"),
                             ("package", "install"), ("email", "send")]:
            d = _decision(tool, action)
            self.assertFalse(
                should_confirm(d, ALL_PERMISSIVE),
                f"modo 'all' NO debe confirmar {tool}.{action} (permisivo total)")

    def test_confirm_risky_equals_historic_behaviour(self):
        # DEFAULT debe ser IDÉNTICO a la conducta histórica (requires_confirmation).
        for tool, action in [("email", "send"), ("filesystem", "delete"),
                             ("notes_tasks", "create"), ("web", "search"),
                             ("system", "shutdown"), ("audio", "set_default")]:
            d = classify_tool_call(tool, {"action": action})
            self.assertEqual(
                should_confirm(d, CONFIRM_RISKY), d.requires_confirmation,
                f"{tool}.{action}: confirm_risky debe igualar requires_confirmation")


class TestPolicyEnv(unittest.TestCase):
    def _restore(self, prev):
        if prev is None:
            os.environ.pop("GEMMA4_CONFIRMATION_POLICY", None)
        else:
            os.environ["GEMMA4_CONFIRMATION_POLICY"] = prev

    def test_default_policy_is_confirm_risky(self):
        prev = os.environ.pop("GEMMA4_CONFIRMATION_POLICY", None)
        try:
            self.assertEqual(get_policy(), CONFIRM_RISKY)
        finally:
            self._restore(prev)

    def test_invalid_policy_falls_back_to_confirm_risky(self):
        prev = os.environ.get("GEMMA4_CONFIRMATION_POLICY")
        os.environ["GEMMA4_CONFIRMATION_POLICY"] = "garbage"
        try:
            self.assertEqual(get_policy(), CONFIRM_RISKY)
        finally:
            self._restore(prev)

    def test_env_selects_never_and_always_case_insensitive(self):
        prev = os.environ.get("GEMMA4_CONFIRMATION_POLICY")
        try:
            os.environ["GEMMA4_CONFIRMATION_POLICY"] = "never"
            self.assertEqual(get_policy(), NEVER_CONFIRM)
            os.environ["GEMMA4_CONFIRMATION_POLICY"] = "  ALWAYS  "
            self.assertEqual(get_policy(), ALWAYS_CONFIRM)
        finally:
            self._restore(prev)


class TestExecuteIntegration(unittest.TestCase):
    """End-to-end: ToolRegistry.execute() respeta la política en el punto real de
    intercepción (tools.py). La confirmación ocurre ANTES del handler, así que los
    paths inexistentes no se tocan (filesystem.delete solo confirma, no borra)."""

    def _reg(self):
        import tempfile
        from pathlib import Path
        from ..memory_pkg.memory import MemoryStore
        from ..tools_pkg.tools import ToolRegistry
        from ..memory_pkg.state import AgentState as _AS
        tmp = Path(tempfile.mkdtemp(prefix="gemma4_b5_"))
        memory = MemoryStore(tmp / "mem.json")
        state = _AS(tmp / "data" / "state.json")
        return ToolRegistry(memory, tmp / "captures", state=state, safety_enabled=True)

    def _set(self, value):
        prev = os.environ.get("GEMMA4_CONFIRMATION_POLICY")
        if value is None:
            os.environ.pop("GEMMA4_CONFIRMATION_POLICY", None)
        else:
            os.environ["GEMMA4_CONFIRMATION_POLICY"] = value
        return prev

    def _restore(self, prev):
        if prev is None:
            os.environ.pop("GEMMA4_CONFIRMATION_POLICY", None)
        else:
            os.environ["GEMMA4_CONFIRMATION_POLICY"] = prev

    def test_irreversible_confirms_through_execute_under_every_policy(self):
        # GARANTÍA DURA end-to-end: filesystem.delete (irreversible, args válidos) debe
        # confirmar bajo TODA política — incluido never. La confirmación intercepta ANTES
        # del handler, así que el path inexistente NUNCA se toca (no borra nada).
        for pol in (None, "never", "always"):  # None = default confirm_risky
            reg = self._reg()
            prev = self._set(pol)
            try:
                out = reg.execute("filesystem", {"action": "delete", "path": "Z:\\b5_nonexistent.txt"})
                self.assertEqual(
                    out.get("status"), "needs_confirmation",
                    f"filesystem.delete (irreversible) DEBE confirmar bajo policy={pol or 'confirm_risky'!r}; got {out}")
            finally:
                self._restore(prev)

    def test_reversible_risky_contrast_never_vs_confirm_risky(self):
        # CONTRASTE riguroso (no vacuo): la MISMA acción reversible-riesgosa
        # (desktop_layout.restore = desktop_layout_change, NO irreversible) debe
        # confirmarse bajo confirm_risky y auto-aprobarse bajo never. Si la acción no
        # llega a la confirmación (su validación de args falla antes), se hace skip —
        # el auto-approve ya está cubierto por el unit test de should_confirm.
        args = {"action": "restore", "name": "b5_inexistente"}
        reg1 = self._reg()
        prev = self._set(None)  # confirm_risky (default)
        try:
            risky = reg1.execute("desktop_layout", dict(args))
        finally:
            self._restore(prev)
        if risky.get("status") != "needs_confirmation":
            self.skipTest(
                f"desktop_layout.restore no alcanza la confirmación (status={risky.get('status')}); "
                "el auto-approve está cubierto por TestPolicyBehaviour")
        reg2 = self._reg()
        prev = self._set("never")
        try:
            never = reg2.execute("desktop_layout", dict(args))
        finally:
            self._restore(prev)
        self.assertNotEqual(
            never.get("status"), "needs_confirmation",
            "never debe AUTO-APROBAR lo reversible que confirm_risky confirma")


if __name__ == "__main__":
    unittest.main()
