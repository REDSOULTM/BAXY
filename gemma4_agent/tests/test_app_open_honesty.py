"""app.open honesto tri-estado.

Antes app_open devolvía verified=False explícito cuando el auto-verify NO
confirmaba la ventana. Eso (a) peleaba con _normalize_tool_result (que mapea
launch_requested -> verified=None) y (b) disparaba el guard "no dejó evidencia"
+ reintentos = el flakeo events=0 medido. "No confirmé la ventana" NO es "falló":
es "no medible aún" (la app puede seguir cargando). Tri-estado:
  - app verificada (ventana/proceso encontrado)  -> verified=True,  status=done
  - app ya estaba abierta (preexisting)           -> verified=True,  status=done
  - launch despachado, no confirmado en la ventana -> verified=None, status=dispatched
  - resolver no encontró la app / open() falló     -> _err (ok=False)

Tests con apps mockeadas (NO se lanza ninguna app real; sin input sintético).
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from gemma4_agent.tools_pkg.tools import ToolRegistry, _normalize_tool_result


def _reg_with(open_ok=True, verify_found_sequence=None, preexisting_found=False):
    """ToolRegistry mínimo con apps/verify/state mockeados para ejercer app_open."""
    reg = ToolRegistry.__new__(ToolRegistry)

    cand = MagicMock()
    cand.process_name = "discord.exe"
    cand.as_dict.return_value = {"name": "Discord", "launch": "discord.exe"}

    reg.apps = MagicMock()
    reg.apps.find.return_value = [cand]
    reg.apps.open.return_value = {"ok": open_ok, "error": None if open_ok else "boom"}

    reg.state = MagicMock()
    reg.state.register_resource.return_value = {"resource": {"id": "r1"}}

    # verify_app_opened: 1ª llamada = preexisting; siguientes = post-launch.
    seq = list(verify_found_sequence or [])
    calls = {"n": 0}

    def _verify(args):
        idx = calls["n"]
        calls["n"] += 1
        if idx == 0:
            return {"found": preexisting_found}
        found = seq.pop(0) if seq else False
        return {"found": found, "match": {"title": "Discord"} if found else None}

    reg.verify_app_opened = _verify
    return reg


class AppOpenHonestyTest(unittest.TestCase):

    def test_verified_when_window_appears(self):
        reg = _reg_with(verify_found_sequence=[True])
        r = reg.app_open({"name": "Discord"})
        r = _normalize_tool_result("app", {"action": "open", "name": "Discord"}, r)
        self.assertTrue(r["ok"])
        self.assertIs(r["verified"], True)
        self.assertEqual(r["completion_status"], "launch_verified")

    def test_unconfirmed_launch_is_none_not_false(self):
        # El launch se despachó OK pero la ventana no apareció en la ventana de
        # auto-verify. NO es 'falló' -> verified=None (no medible, sigue cargando).
        reg = _reg_with(verify_found_sequence=[False, False, False])
        r = reg.app_open({"name": "Discord"})
        r = _normalize_tool_result("app", {"action": "open", "name": "Discord"}, r)
        self.assertTrue(r["ok"])
        self.assertIsNone(r["verified"], "launch no confirmado debe ser None, no False")
        self.assertEqual(r["completion_status"], "launch_requested")
        self.assertEqual(r["status"], "dispatched")

    def test_preexisting_app_is_verified(self):
        reg = _reg_with(verify_found_sequence=[False], preexisting_found=True)
        r = reg.app_open({"name": "Discord"})
        r = _normalize_tool_result("app", {"action": "open", "name": "Discord"}, r)
        self.assertIs(r["verified"], True)
        self.assertTrue(r["preexisting"])

    def test_open_failure_is_honest_error(self):
        reg = _reg_with(open_ok=False)
        r = reg.app_open({"name": "Discord"})
        self.assertFalse(r["ok"])
        self.assertEqual(r.get("status"), "failed")

    def test_app_not_found_is_error(self):
        reg = _reg_with()
        reg.apps.find.return_value = []
        r = reg.app_open({"name": "Nonexistent App ZZZ"})
        self.assertFalse(r["ok"])

    def test_unconfirmed_does_not_trigger_unverified_guard(self):
        # _has_unverified_signal NO debe marcar el launch no-confirmado como
        # needs_verification (era la causa del guard "no dejó evidencia" + retry).
        from gemma4_agent.tools_pkg.tools import _has_unverified_signal
        reg = _reg_with(verify_found_sequence=[False, False, False])
        r = reg.app_open({"name": "Discord"})
        r = _normalize_tool_result("app", {"action": "open", "name": "Discord"}, r)
        self.assertFalse(_has_unverified_signal(r),
                         "launch_requested + verified=None no es unverified-signal")


class AppOpenFalsePositiveGateTest(unittest.TestCase):
    """GATE: 0 false-positive de verified con proceso
    AUSENTE. El tool nunca debe declarar verified=True si el estado del SO no
    confirma proceso/ventana. Ejercemos la cascada con la app NO apareciendo.
    """

    def test_absent_process_never_verified_true(self):
        # La app no aparece en NINGÚN chequeo (preexisting=False, post=False*3).
        # GATE: verified DEBE ser None (no medible), JAMÁS True.
        reg = _reg_with(verify_found_sequence=[False, False, False],
                        preexisting_found=False)
        r = reg.app_open({"name": "Discord"})
        self.assertTrue(r["ok"], "el launch se despachó sin error")
        self.assertIsNot(r["verified"], True,
                         "FALSE-POSITIVE: verified=True con proceso ausente")
        self.assertIsNone(r["verified"])
        self.assertEqual(r["completion_status"], "launch_requested")

    def test_verifier_never_confirms_absent_process(self):
        # El VERIFIER estructural (lee tasklist real) no debe confirmar una app
        # ausente. Mockeamos _running_process_names a vacío y verified=None del
        # tool -> el verifier hace su propio check y NO halla el proceso.
        import gemma4_agent.verifiers  # noqa: F401  registra decorators
        from gemma4_agent.safety_pkg.verify_core import verify
        from unittest import mock
        result = {"ok": True, "verified": None, "status": "dispatched",
                  "completion_status": "launch_requested"}
        with mock.patch("gemma4_agent.tools_pkg.tools._running_process_names",
                        return_value=set()):
            out = verify("app", {"action": "open", "name": "Discord"}, result)
        # proceso ausente -> NUNCA confirmed=True (a lo sumo None "no medible").
        self.assertIsNot(out.confirmed, True,
                         "FALSE-POSITIVE: verifier confirmó app ausente")

    def test_verifier_confirms_present_process(self):
        # Control positivo: si el proceso SÍ está, el verifier confirma.
        import gemma4_agent.verifiers  # noqa: F401
        from gemma4_agent.safety_pkg.verify_core import verify
        from unittest import mock
        result = {"ok": True, "verified": None, "status": "dispatched",
                  "completion_status": "launch_requested"}
        with mock.patch("gemma4_agent.tools_pkg.tools._running_process_names",
                        return_value={"discord.exe"}):
            out = verify("app", {"action": "open", "name": "Discord"}, result)
        self.assertIs(out.confirmed, True)
        self.assertIn("app:Discord", out.evidence_keys)


if __name__ == "__main__":
    unittest.main()
